"""Tiny local HTTP API and static server for the React dashboard.

The analysis and collection scripts remain standalone. This file only exposes
their data/actions to the UI and runs one daily collection while it is open.
"""

import datetime
import json
import mimetypes
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import requests
from collector import collect_all_apps
from db import get_connection, init_db
from difficulty import calculate_difficulty
from init_db import fetch_app_details

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist")
SEARCHES_DIR = os.path.join(BASE_DIR, "data", "searches")
HOST = os.environ.get("ASO_HOST", "127.0.0.1")
PORT = int(os.environ.get("ASO_PORT", "8501"))
DAILY_HOUR = int(os.environ.get("ASO_DAILY_HOUR", "6"))

collection_state = {"running": False, "lastRun": None, "error": None, "dailyHour": DAILY_HOUR}
collection_lock = threading.Lock()


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def rows_as_dicts(cursor):
    return [dict(row) for row in cursor.fetchall()]


def list_apps():
    conn = get_connection()
    cursor = conn.execute("""
        SELECT a.*, COUNT(DISTINCT k.id) AS keyword_count, MAX(r.date) AS last_update
        FROM apps a
        LEFT JOIN keywords k ON k.app_id = a.id AND k.active = 1
        LEFT JOIN rankings r ON r.keyword_id = k.id
        GROUP BY a.id
        ORDER BY a.id
    """)
    apps = rows_as_dicts(cursor)
    conn.close()
    return apps


def search_apps(query, country):
    response = requests.get("https://itunes.apple.com/search", params={
        "term": query,
        "country": country,
        "entity": "software",
        "limit": 20,
    }, timeout=12)
    response.raise_for_status()
    return [{
        "app_store_id": str(item.get("trackId")),
        "name": item.get("trackName", "Unknown App"),
        "developer": item.get("artistName", "Unknown Developer"),
        "version": item.get("version", "—"),
        "icon_url": item.get("artworkUrl100"),
    } for item in response.json().get("results", []) if item.get("trackId")]


def read_snapshot(keyword, country, app_store_id):
    path = os.path.join(SEARCHES_DIR, f"{slugify(keyword)}-{country}-latest.json")
    try:
        with open(path, "r", encoding="utf-8") as file:
            snapshot = json.load(file)
        results = snapshot.get("results", [])
        rank = next((item.get("position") for item in results
                     if str(item.get("app_store_id")) == str(app_store_id)), None)
        return {
            "searched_at": snapshot.get("searched_at"),
            "apps": results[:5],
            "rank": rank,
            "difficulty": calculate_difficulty(keyword, results)["score"] if results else None,
        }
    except (OSError, json.JSONDecodeError):
        return {"searched_at": None, "apps": [], "rank": None, "difficulty": None}


def list_keywords(app_id):
    conn = get_connection()
    app = conn.execute("SELECT * FROM apps WHERE id = ?", (app_id,)).fetchone()
    if not app:
        conn.close()
        return None

    keywords = rows_as_dicts(conn.execute(
        "SELECT * FROM keywords WHERE app_id = ? AND active = 1 ORDER BY id", (app_id,)
    ))
    for keyword in keywords:
        history = rows_as_dicts(conn.execute("""
            SELECT date, rank, difficulty FROM rankings
            WHERE keyword_id = ? ORDER BY id DESC LIMIT 2
        """, (keyword["id"],)))
        latest = history[0] if history else {}
        previous = history[1] if len(history) > 1 else {}
        snapshot = read_snapshot(keyword["keyword"], app["country"], app["app_store_id"])
        current_rank = snapshot["rank"] if snapshot["searched_at"] else latest.get("rank")
        previous_rank = previous.get("rank")
        change = None
        if current_rank is not None and previous_rank is not None:
            change = previous_rank - current_rank
        keyword.update({
            "rank": current_rank,
            "difficulty": snapshot["difficulty"] if snapshot["searched_at"] else latest.get("difficulty"),
            "last_update": snapshot["searched_at"] or latest.get("date"),
            "change": change,
            "competitors": snapshot["apps"],
        })
    conn.close()
    return keywords


def keyword_history(app_id, scope="30"):
    conn = get_connection()
    app = conn.execute("SELECT id, current_version FROM apps WHERE id = ?", (app_id,)).fetchone()
    if not app:
        conn.close()
        return None
    if scope == "version":
        history_filter = "r.app_version = ?"
        history_value = app["current_version"]
        scope_label = f"Version {app['current_version']}"
    else:
        try:
            days = int(scope)
        except ValueError:
            days = 30
        days = days if days in (7, 15, 30) else 30
        history_filter = "r.date >= ?"
        history_value = (datetime.date.today() - datetime.timedelta(days=days - 1)).isoformat()
        scope_label = f"Last {days} days"
    rows = rows_as_dicts(conn.execute("""
        SELECT k.id AS keyword_id, k.keyword, r.date, r.rank, r.difficulty
        FROM keywords k
        LEFT JOIN rankings r ON r.keyword_id = k.id AND """ + history_filter + """
        WHERE k.app_id = ? AND k.active = 1
        ORDER BY k.id, r.date, r.id
    """, (history_value, app_id)))
    conn.close()

    grouped = {}
    for row in rows:
        item = grouped.setdefault(row["keyword_id"], {
            "keyword_id": row["keyword_id"], "keyword": row["keyword"], "points": []
        })
        if not row["date"]:
            continue
        point = {key: row[key] for key in ("date", "rank", "difficulty")}
        if item["points"] and item["points"][-1]["date"] == point["date"]:
            item["points"][-1] = point
        else:
            item["points"].append(point)
    return {"scope": scope, "scope_label": scope_label, "series": list(grouped.values())}


def run_collection():
    if not collection_lock.acquire(blocking=False):
        return False
    collection_state.update({"running": True, "error": None})

    def work():
        try:
            collect_all_apps()
            collection_state["lastRun"] = datetime.datetime.now().isoformat(timespec="seconds")
        except BaseException as error:
            collection_state["error"] = str(error)
        finally:
            collection_state["running"] = False
            collection_lock.release()

    threading.Thread(target=work, daemon=True).start()
    return True


def daily_scheduler():
    """Run once per local day after DAILY_HOUR while the dashboard is open."""
    conn = get_connection()
    latest = conn.execute("SELECT MAX(date) AS date FROM rankings").fetchone()["date"]
    conn.close()
    last_started = latest
    while True:
        now = datetime.datetime.now()
        today = now.date().isoformat()
        if now.hour >= DAILY_HOUR and last_started != today and run_collection():
            last_started = today
        time.sleep(60)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(f"[web] {self.address_string()} - {format % args}")

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/apps":
            return self.send_json(list_apps())
        if path == "/api/app-search":
            params = parse_qs(parsed.query)
            query = params.get("query", [""])[0].strip()
            country = params.get("country", ["us"])[0].strip().lower()
            if len(query) < 2:
                return self.send_json({"error": "Enter at least two characters."}, 400)
            if not re.fullmatch(r"[a-z]{2}", country):
                return self.send_json({"error": "Invalid storefront."}, 400)
            try:
                return self.send_json(search_apps(query, country))
            except requests.RequestException as error:
                return self.send_json({"error": f"App Store search failed: {error}"}, 502)
        if path == "/api/status":
            return self.send_json(collection_state)
        match = re.fullmatch(r"/api/apps/(\d+)/keywords", path)
        if match:
            keywords = list_keywords(int(match.group(1)))
            status = 200 if keywords is not None else 404
            return self.send_json(keywords if keywords is not None else {"error": "App not found"}, status)
        match = re.fullmatch(r"/api/apps/(\d+)/history", path)
        if match:
            params = parse_qs(parsed.query)
            scope = params.get("range", ["30"])[0]
            history = keyword_history(int(match.group(1)), scope)
            status = 200 if history is not None else 404
            return self.send_json(history if history is not None else {"error": "App not found"}, status)
        self.serve_static(path)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            payload = self.read_json()
            if path == "/api/apps":
                return self.create_app(payload)
            if path == "/api/collect":
                started = run_collection()
                return self.send_json({"started": started}, 202 if started else 409)
            match = re.fullmatch(r"/api/apps/(\d+)/keywords", path)
            if match:
                return self.create_keywords(int(match.group(1)), payload)
            return self.send_json({"error": "Not found"}, 404)
        except (ValueError, json.JSONDecodeError) as error:
            return self.send_json({"error": str(error)}, 400)
        except Exception as error:
            return self.send_json({"error": str(error)}, 500)

    def do_DELETE(self):
        path = urlparse(self.path).path
        match = re.fullmatch(r"/api/keywords/(\d+)", path)
        if not match:
            return self.send_json({"error": "Not found"}, 404)
        conn = get_connection()
        conn.execute("UPDATE keywords SET active = 0 WHERE id = ?", (int(match.group(1)),))
        conn.commit()
        conn.close()
        self.send_json({"ok": True})

    def create_app(self, payload):
        app_store_ids = payload.get("appStoreIds") or [payload.get("appStoreId", "")]
        app_store_ids = list(dict.fromkeys(str(value).strip() for value in app_store_ids if str(value).strip()))
        country = str(payload.get("country", "us")).strip().lower()
        if not app_store_ids or any(not value.isdigit() for value in app_store_ids) or not re.fullmatch(r"[a-z]{2}", country):
            raise ValueError("Select an app or enter numeric App Store IDs.")
        conn = get_connection()
        saved = []
        for app_store_id in app_store_ids:
            details = fetch_app_details(app_store_id, country)
            if not details:
                continue
            conn.execute("""
                INSERT INTO apps (app_store_id, name, country, current_version, icon_url)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(app_store_id) DO UPDATE SET
                  name = excluded.name, country = excluded.country,
                  current_version = excluded.current_version, icon_url = excluded.icon_url
            """, (app_store_id, details.get("trackName", "Unknown App"), country,
                  details.get("version", "—"), details.get("artworkUrl100")))
            saved.append(app_store_id)
        if not saved:
            conn.close()
            raise ValueError("No selected apps were found in this storefront.")
        conn.commit()
        placeholders = ",".join("?" for _ in saved)
        apps = rows_as_dicts(conn.execute(f"SELECT * FROM apps WHERE app_store_id IN ({placeholders}) ORDER BY id", saved))
        conn.close()
        self.send_json({"apps": apps}, 201)

    def create_keywords(self, app_id, payload):
        values = payload.get("keywords", [])
        if isinstance(values, str):
            values = values.splitlines()
        keywords = list(dict.fromkeys(value.strip().lower() for value in values if value.strip()))
        if not keywords:
            raise ValueError("Add at least one keyword.")
        conn = get_connection()
        if not conn.execute("SELECT 1 FROM apps WHERE id = ?", (app_id,)).fetchone():
            conn.close()
            return self.send_json({"error": "App not found"}, 404)
        for keyword in keywords:
            conn.execute("""
                INSERT INTO keywords (app_id, keyword, active) VALUES (?, ?, 1)
                ON CONFLICT(app_id, keyword) DO UPDATE SET active = 1
            """, (app_id, keyword))
        conn.commit()
        conn.close()
        self.send_json({"added": len(keywords)}, 201)

    def serve_static(self, path):
        if not os.path.isdir(DIST_DIR):
            return self.send_json({"error": "Frontend not built. Run npm install && npm run build in frontend/."}, 503)
        relative = path.lstrip("/") or "index.html"
        candidate = os.path.abspath(os.path.join(DIST_DIR, relative))
        if not candidate.startswith(os.path.abspath(DIST_DIR)) or not os.path.isfile(candidate):
            candidate = os.path.join(DIST_DIR, "index.html")
        with open(candidate, "rb") as file:
            body = file.read()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(candidate)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    init_db()
    threading.Thread(target=daily_scheduler, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"ASO Tracker running at http://{HOST}:{PORT}")
    print(f"Daily collection is scheduled after {DAILY_HOUR:02d}:00 while this server is open.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")


if __name__ == "__main__":
    main()
