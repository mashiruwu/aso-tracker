import math
import sys
import json
import os
import re

RATING_STRENGTH_WEIGHT = 0.50
LARGE_COMPETITOR_WEIGHT = 0.25
TITLE_COMPETITION_WEIGHT = 0.25

LARGE_COMPETITOR_THRESHOLD = 100000

STOP_WORDS = {"a", "an", "the", "for", "and", "of", "to", "in", "on", "with", "by", "is", "it"}

def slugify(text):
    text = text.lower()
    return re.sub(r'[^a-z0-9]+', '-', text).strip('-')

def _normalize_string(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def get_tokens(text):
    norm = _normalize_string(text)
    tokens = norm.split()
    return [t for t in tokens if t not in STOP_WORDS]

def calculate_rating_strength(top_10):
    if not top_10:
        return 0
        
    log_ratings = []
    for app in top_10:
        rating_count = app.get("rating_count")
        if rating_count is None:
            rating_count = 0
        log_ratings.append(math.log10(rating_count + 1))
        
    log_ratings.sort()
    mid = len(log_ratings) // 2
    if len(log_ratings) % 2 == 0:
        median_log = (log_ratings[mid - 1] + log_ratings[mid]) / 2.0
    else:
        median_log = log_ratings[mid]
        
    # Normalize: log value 1 -> 0, log value 6 -> 100
    score = ((median_log - 1) / (6 - 1)) * 100
    score = max(0, min(100, score))
    return int(round(score))

def calculate_large_competitors(top_10):
    if not top_10:
        return 0
    large_count = 0
    for app in top_10:
        rc = app.get("rating_count")
        if rc is not None and rc >= LARGE_COMPETITOR_THRESHOLD:
            large_count += 1
            
    score = (large_count / len(top_10)) * 100
    return int(round(score))

def calculate_title_competition(keyword, top_10):
    if not top_10:
        return 0
        
    kw_tokens = get_tokens(keyword)
    if not kw_tokens:
        return 0
        
    app_scores = []
    for app in top_10:
        title = app.get("name", "")
        title_tokens = get_tokens(title)
        
        matches = sum(1 for t in kw_tokens if t in title_tokens)
        if matches == len(kw_tokens):
            app_scores.append(100)
        elif matches > 0:
            app_scores.append(50)
        else:
            app_scores.append(0)
            
    avg_score = sum(app_scores) / len(app_scores)
    return int(round(avg_score))

def get_difficulty_label(score):
    if score <= 24:
        return "Low"
    elif score <= 49:
        return "Medium"
    elif score <= 74:
        return "High"
    else:
        return "Very High"

def calculate_difficulty(keyword: str, results: list) -> dict:
    top_10 = results[:10]
    
    rating_strength = calculate_rating_strength(top_10)
    large_competitors = calculate_large_competitors(top_10)
    title_competition = calculate_title_competition(keyword, top_10)
    
    difficulty = (
        rating_strength * RATING_STRENGTH_WEIGHT +
        large_competitors * LARGE_COMPETITOR_WEIGHT +
        title_competition * TITLE_COMPETITION_WEIGHT
    )
    
    final_score = int(round(max(0, min(100, difficulty))))
    
    return {
        "score": final_score,
        "label": get_difficulty_label(final_score),
        "rating_strength": rating_strength,
        "large_competitors": large_competitors,
        "title_competition": title_competition
    }

def main():
    if len(sys.argv) < 2:
        print("Usage: python difficulty.py <keyword> [country_code]")
        sys.exit(1)
        
    keyword = sys.argv[1]
    country = sys.argv[2] if len(sys.argv) > 2 else "us"
    
    json_path = os.path.join("data", "searches", f"{slugify(keyword)}-{country}-latest.json")
    if not os.path.exists(json_path):
        print(f"No search snapshot found.")
        print(f"Run check_rankings.py first.")
        sys.exit(1)
        
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        sys.exit(1)
        
    results = data.get("results", [])
    diff_data = calculate_difficulty(keyword, results)
    
    print(f"Keyword: {keyword}\n")
    print(f"Difficulty: {diff_data['score']}/100 — {diff_data['label']}\n")
    print("Breakdown:\n")
    print(f"Rating Strength      {diff_data['rating_strength']}")
    print(f"Large Competitors    {diff_data['large_competitors']}")
    print(f"Title Competition    {diff_data['title_competition']}")

if __name__ == "__main__":
    main()
