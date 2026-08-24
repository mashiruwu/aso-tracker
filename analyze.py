import csv
import json
import os
import sys
import re
from difficulty import calculate_difficulty

def slugify(text):
    text = text.lower()
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')

# --- THRESHOLDS ---
PROTECT_RANK_THRESHOLD = 10
TARGET_RANK_MIN = 11
TARGET_RANK_MAX = 40
DEPRIORITIZE_TRENDS = ["Strong decline", "Lost"]
DEPRIORITIZE_DIFFICULTY = ["Very High"]

def get_trend(prev_rank, curr_rank):
    if curr_rank is None and prev_rank is None:
        return "Not ranked"
    if prev_rank is None and curr_rank is not None:
        return "New rank"
    if prev_rank is not None and curr_rank is None:
        return "Lost"
    
    diff = prev_rank - curr_rank
    if diff >= 10:
        return "Strong improvement"
    elif diff >= 1:
        return "Improving"
    elif diff == 0:
        return "Stable"
    elif diff >= -9:
        return "Declining"
    else:
        return "Strong decline"

def get_opportunity(curr_rank, trend, difficulty_label):
    if curr_rank is None:
        return "Low" 
        
    score = 0
    if curr_rank <= 10:
        score = 0 
    elif 11 <= curr_rank <= 30:
        score = 2 
    elif 31 <= curr_rank <= 70:
        score = 1 
    else:
        score = 0 
        
    if trend in ["Strong improvement", "Improving"]:
        score += 1
    elif trend in ["Declining", "Strong decline", "Lost"]:
        score -= 1
        
    if difficulty_label in ["Very High", "High"]:
        score -= 1
    elif difficulty_label in ["Low", "Medium"]:
        score += 1
        
    if score >= 2:
        return "High"
    elif score == 1:
        return "Medium"
    else:
        return "Low"

def get_metadata_priority(curr_rank, trend, difficulty_label):
    if curr_rank is None:
        return "Deprioritize"
        
    if curr_rank <= PROTECT_RANK_THRESHOLD:
        return "Protect"
        
    if TARGET_RANK_MIN <= curr_rank <= TARGET_RANK_MAX:
        if trend in DEPRIORITIZE_TRENDS or difficulty_label in DEPRIORITIZE_DIFFICULTY:
            return "Deprioritize"
        return "Target"
        
    return "Deprioritize"

def main():
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except Exception:
        print("Error reading config.json")
        sys.exit(1)
        
    country = config.get("country", "us")
    
    try:
        with open("keywords.txt", "r") as f:
            keywords = [line.strip() for line in f if line.strip()]
    except Exception:
        print("Error reading keywords.txt")
        sys.exit(1)
        
    history = {kw: [] for kw in keywords}
    csv_path = os.path.join("data", "rankings.csv")
    
    if os.path.exists(csv_path):
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                kw = row["keyword"]
                if row["country"] == country and kw in history:
                    rank_str = row["rank"]
                    rank_val = int(rank_str) if rank_str else None
                    history[kw].append(rank_val)
                    
    report_data = []
    
    for kw in keywords:
        ranks = history[kw]
        
        curr_rank = ranks[-1] if len(ranks) > 0 else None
        prev_rank = ranks[-2] if len(ranks) > 1 else None
        
        valid_ranks = [r for r in ranks if r is not None]
        best_rank = min(valid_ranks) if valid_ranks else None
        
        trend = get_trend(prev_rank, curr_rank)
        
        json_path = os.path.join("data", "searches", f"{slugify(kw)}-{country}-latest.json")
        diff_data = None
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                search_data = json.load(f)
                diff_data = calculate_difficulty(kw, search_data.get("results", []))
                
        diff_label = diff_data["label"] if diff_data else "Unknown"
        opp = get_opportunity(curr_rank, trend, diff_label)
        priority = get_metadata_priority(curr_rank, trend, diff_label)
        
        change_val = None
        if prev_rank is not None and curr_rank is not None:
            change_val = prev_rank - curr_rank
            
        report_data.append({
            "keyword": kw,
            "curr_rank": curr_rank,
            "prev_rank": prev_rank,
            "best_rank": best_rank,
            "change": change_val,
            "trend": trend,
            "difficulty": diff_data,
            "opportunity": opp,
            "priority": priority
        })
        
    print("ASO REPORT")
    print("==========\n")
    
    for opp_level in ["High", "Medium", "Low"]:
        items = [d for d in report_data if d["opportunity"] == opp_level]
        if not items:
            continue
            
        print(f"{opp_level.upper()} OPPORTUNITY\n")
        
        for idx, item in enumerate(items, 1):
            print(f"{idx}. {item['keyword']}\n")
            
            if item['curr_rank'] is None:
                print("   Current Rank: Not ranked")
            else:
                print(f"   Current Rank: #{item['curr_rank']}")
                
            if item['prev_rank'] is not None:
                print(f"   Previous Rank: #{item['prev_rank']}")
                
            if item['change'] is not None:
                sign = "+" if item['change'] > 0 else ""
                print(f"   Change: {sign}{item['change']}")
                
            print(f"   Trend: {item['trend']}\n")
            
            diff_data = item['difficulty']
            if diff_data:
                print(f"   Difficulty: {diff_data['score']}/100 — {diff_data['label']}\n")
                print("   Difficulty breakdown:")
                print(f"     Rating Strength:      {diff_data['rating_strength']}")
                print(f"     Large Competitors:    {diff_data['large_competitors']}")
                print(f"     Title Competition:    {diff_data['title_competition']}")
            else:
                print("   Difficulty: Unknown")
                
            if item['best_rank'] is not None and item['best_rank'] != item['curr_rank']:
                print(f"\n   Best Historical Rank: #{item['best_rank']}")
                
            print("\n" + "-" * 40 + "\n")

    print("METADATA PRIORITIES")
    print("===================\n")
    
    for prio_level in ["Protect", "Target", "Deprioritize"]:
        items = [d for d in report_data if d["priority"] == prio_level]
        if not items:
            continue
            
        print(f"{prio_level.upper()}\n")
        
        for item in items:
            print(f"{item['keyword']}")
            
            change_str = ""
            if item['change'] is not None and item['change'] != 0:
                sign = "↑" if item['change'] > 0 else "↓"
                change_str = f" {sign}{abs(item['change'])}"
                
            if item['curr_rank'] is None:
                print("Rank: Not ranked")
            else:
                print(f"Rank: #{item['curr_rank']}{change_str}")
                
            diff_data = item['difficulty']
            if diff_data:
                print(f"Difficulty: {diff_data['score']} — {diff_data['label']}")
            else:
                print("Difficulty: Unknown")
                
            if prio_level == "Deprioritize":
                if diff_data and diff_data['label'] in DEPRIORITIZE_DIFFICULTY:
                    print(f"{diff_data['label']} Competition")
                elif item['trend'] in DEPRIORITIZE_TRENDS:
                    print(f"Trend: {item['trend']}")
                        
            print("")

if __name__ == "__main__":
    main()
