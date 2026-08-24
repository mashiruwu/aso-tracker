import sys
import json
from search import search_app_store

def main():
    if len(sys.argv) < 2:
        print("Usage: python rank.py <keyword>")
        print("Example: python rank.py \"ai flashcards\"")
        sys.exit(1)
        
    keyword = sys.argv[1]
    
    try:
        with open("config.json", "r") as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading config.json: {e}")
        sys.exit(1)
        
    target_app_id = str(config.get("app_store_id"))
    country = config.get("country", "us")
    
    print(f"Keyword: {keyword}")
    print(f"Country: {country.upper()}\n")
    
    # We use limit=200 for rank checking as per instructions
    results = search_app_store(keyword, country, limit=200)
    
    target_index = -1
    for i, result in enumerate(results):
        if str(result.get("trackId")) == target_app_id:
            target_index = i
            break
            
    if target_index == -1:
        print("Your rank: Not ranked in top 200")
    else:
        print(f"Your rank: #{target_index + 1}")
        
        if target_index > 0:
            print("\nApps above you:\n")
            start_idx = max(0, target_index - 3)
            for i in range(start_idx, target_index):
                app_name = results[i].get("trackName", "Unknown App")
                print(f"#{i+1} {app_name}")
                
        print("\nYour app:")
        target_app_name = results[target_index].get("trackName", "Unknown App")
        print(f"#{target_index+1} {target_app_name}")

if __name__ == "__main__":
    main()
