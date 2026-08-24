import time
import json
import sys
import os
import csv
import re
from datetime import datetime
from search import search_app_store

def slugify(text):
    text = text.lower()
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')

def main():
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading config.json: {e}")
        sys.exit(1)
        
    target_app_id = str(config.get("app_store_id"))
    country = config.get("country", "us")
    
    try:
        with open("keywords.txt", "r") as f:
            keywords = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("Error: keywords.txt not found.")
        sys.exit(1)
        
    os.makedirs(os.path.join("data", "searches"), exist_ok=True)
    csv_path = os.path.join("data", "rankings.csv")
    
    # Load previous rankings
    last_ranks = {}
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["country"] == country:
                    rank_str = row["rank"]
                    last_ranks[row["keyword"]] = int(rank_str) if rank_str else None
                    
    print(f"Checking {len(keywords)} keywords...\n")
    
    ranked_count = 0
    not_ranked_count = 0
    
    results_to_save = []
    tabular_summary = []
    current_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    for keyword in keywords:
        search_results = search_app_store(keyword, country, limit=200)
        
        target_index = -1
        structured_results = []
        
        for i, result in enumerate(search_results):
            app_id = str(result.get("trackId"))
            if app_id == target_app_id:
                target_index = i
                
            structured_results.append({
                "position": i + 1,
                "app_store_id": app_id,
                "name": result.get("trackName", "Unknown App"),
                "developer": result.get("artistName", "Unknown Developer"),
                "rating": result.get("averageUserRating"),
                "rating_count": result.get("userRatingCount"),
                "genre": result.get("primaryGenreName"),
                "icon_url": result.get("artworkUrl100")
            })
                
        curr_rank = target_index + 1 if target_index != -1 else None
        
        # Save JSON
        keyword_slug = slugify(keyword)
        json_filename = f"{keyword_slug}-{country}-latest.json"
        json_path = os.path.join("data", "searches", json_filename)
        
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump({
                "keyword": keyword,
                "country": country,
                "searched_at": current_time,
                "results": structured_results
            }, jf, indent=2, ensure_ascii=False)
            
        # Determine change string
        prev_rank = last_ranks.get(keyword, "NO_DATA")
        
        change_str = ""
        if prev_rank == "NO_DATA":
            change_str = "New"
        elif prev_rank is None and curr_rank is not None:
            change_str = "New rank"
        elif prev_rank is not None and curr_rank is None:
            change_str = "Lost"
        elif prev_rank is None and curr_rank is None:
            change_str = "—"
        else:
            diff = prev_rank - curr_rank
            if diff > 0:
                change_str = f"+{diff}"
            elif diff < 0:
                change_str = f"{diff}"
            else:
                change_str = "—"
                
        # Terminal Output for this keyword
        print(f"{keyword.upper()}\n")
        
        if curr_rank is None:
            curr_str = "Not ranked"
            not_ranked_count += 1
            print("Your rank: Not ranked in top 200\n")
        else:
            curr_str = f"#{curr_rank}"
            ranked_count += 1
            print(f"Your rank: #{curr_rank}\n")
            
            if target_index > 0:
                print("Apps above you:\n")
                start_idx = max(0, target_index - 5)
                for i in range(start_idx, target_index):
                    print(f"#{i+1:<2} {structured_results[i]['name']}")
                print("")
                
        print("-" * 40 + "\n")
                
        tabular_summary.append(f"{keyword:<20} {curr_str:<10} {change_str}")
        
        # Prepare for CSV
        rank_val = str(curr_rank) if curr_rank is not None else ""
        results_to_save.append({
            "timestamp": current_time,
            "keyword": keyword,
            "country": country,
            "rank": rank_val
        })
        
        time.sleep(1)
        
    # Append to CSV
    file_exists = os.path.exists(csv_path)
    with open(csv_path, "a", newline='', encoding="utf-8") as f:
        fieldnames = ["timestamp", "keyword", "country", "rank"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(results_to_save)
        
    # Print the tabular summary
    print("SUMMARY")
    for line in tabular_summary:
        print(line)
        
    print(f"\nRanked keywords: {ranked_count}")
    print(f"Not ranked: {not_ranked_count}")

if __name__ == "__main__":
    main()
