import json
import os
from db import init_db, get_connection
import requests

def fetch_app_details(app_store_id, country):
    url = "https://itunes.apple.com/lookup"
    params = {"id": app_store_id, "country": country}
    resp = requests.get(url, params=params)
    data = resp.json()
    if data.get("resultCount", 0) > 0:
        return data["results"][0]
    return {}

def main():
    init_db()
    
    if not os.path.exists("config.json"):
        print("config.json not found")
        return
        
    with open("config.json", "r") as f:
        config = json.load(f)
        
    app_store_id = str(config.get("app_store_id"))
    country = config.get("country", "us")
    
    if not app_store_id:
        print("No app_store_id found in config.json")
        return
        
    app_details = fetch_app_details(app_store_id, country)
    app_name = app_details.get("trackName", "Unknown App")
    version = app_details.get("version", "1.0.0")
    
    conn = get_connection()
    c = conn.cursor()
    
    c.execute("""
        INSERT INTO apps (app_store_id, name, country, current_version, icon_url)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(app_store_id) DO UPDATE SET
          name = excluded.name, country = excluded.country,
          current_version = excluded.current_version, icon_url = excluded.icon_url
    """, (app_store_id, app_name, country, version, app_details.get("artworkUrl100")))
              
    # Fetch ID again or after insert
    c.execute("SELECT id FROM apps WHERE app_store_id = ?", (app_store_id,))
    app_id = c.fetchone()["id"]
    
    # Initialize keywords
    if os.path.exists("keywords.txt"):
        with open("keywords.txt", "r") as f:
            keywords = [line.strip() for line in f if line.strip()]
            
        for kw in keywords:
            c.execute("INSERT OR IGNORE INTO keywords (app_id, keyword, active) VALUES (?, ?, 1)", (app_id, kw))
            
    conn.commit()
    conn.close()
    
    print(f"Initialized database with app: {app_name} (v{version})")
    
if __name__ == "__main__":
    main()
