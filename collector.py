import datetime
import json
import os
import re
from db import get_connection
from db import init_db
from init_db import fetch_app_details
from search import search_app_store
from difficulty import calculate_difficulty
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def slugify(text):
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def normalize_result(result, position):
    """Convert Apple's result shape into the shared snapshot/difficulty shape."""
    return {
        "position": position,
        "app_store_id": str(result.get("trackId", result.get("app_store_id", ""))),
        "name": result.get("trackName", result.get("name", "Unknown App")),
        "developer": result.get("artistName", result.get("developer", "Unknown Developer")),
        "rating": result.get("averageUserRating", result.get("rating")),
        "rating_count": result.get("userRatingCount", result.get("rating_count")),
        "genre": result.get("primaryGenreName", result.get("genre")),
        "icon_url": result.get("artworkUrl100", result.get("icon_url")),
    }


def collect_all_apps(sleep_seconds=1):
    init_db()
    conn = get_connection()
    c = conn.cursor()
    
    # 1. Check all apps
    c.execute("SELECT * FROM apps")
    apps = c.fetchall()
    
    for app in apps:
        app_id = app["id"]
        app_store_id = app["app_store_id"]
        country = app["country"]
        db_version = app["current_version"]
        
        print(f"Checking app: {app['name']}")
        
        # Check for release
        app_details = fetch_app_details(app_store_id, country)
        live_version = app_details.get("version", db_version)
        icon_url = app_details.get("artworkUrl100", app["icon_url"])
        c.execute("UPDATE apps SET icon_url = ? WHERE id = ?", (icon_url, app_id))
        
        if live_version != db_version:
            print(f"  -> New version detected: {live_version}")
            # Update app
            c.execute("UPDATE apps SET current_version = ? WHERE id = ?", (live_version, app_id))
            # Log release
            now = datetime.datetime.now().isoformat()
            c.execute("INSERT INTO releases (app_id, version, detected_at) VALUES (?, ?, ?)",
                      (app_id, live_version, now))
            db_version = live_version
            conn.commit()
            
        # 2. Check keywords for this app
        c.execute("SELECT * FROM keywords WHERE app_id = ? AND active = 1", (app_id,))
        keywords = c.fetchall()
        
        today = datetime.date.today().isoformat()
        
        for kw_row in keywords:
            kw_id = kw_row["id"]
            kw_text = kw_row["keyword"]
            
            print(f"  Searching: {kw_text}")
            raw_results = search_app_store(kw_text, country, limit=200)
            results = [normalize_result(result, idx) for idx, result in enumerate(raw_results, 1)]
            
            # Find rank
            rank = None
            for idx, r in enumerate(results, 1):
                if str(r.get("app_store_id")) == str(app_store_id):
                    rank = idx
                    break
                    
            # Calculate difficulty
            diff_data = calculate_difficulty(kw_text, results)
            diff_score = diff_data["score"]

            searches_dir = os.path.join(BASE_DIR, "data", "searches")
            os.makedirs(searches_dir, exist_ok=True)
            snapshot_path = os.path.join(searches_dir, f"{slugify(kw_text)}-{country}-latest.json")
            with open(snapshot_path, "w", encoding="utf-8") as snapshot_file:
                json.dump({
                    "keyword": kw_text,
                    "country": country,
                    "searched_at": datetime.datetime.now().isoformat(timespec="seconds"),
                    "results": results,
                }, snapshot_file, indent=2, ensure_ascii=False)
            
            # Save snapshot
            c.execute('''
            INSERT INTO rankings (keyword_id, date, rank, difficulty, app_version, source)
            VALUES (?, ?, ?, ?, ?, 'live')
            ''', (kw_id, today, rank, diff_score, db_version))
            
            conn.commit()
            
            time.sleep(sleep_seconds) # simple rate limit
            
    conn.close()
    print("Collection complete.")


def main():
    collect_all_apps()

if __name__ == "__main__":
    main()
