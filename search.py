import sys
import requests

def search_app_store(keyword, country, limit=50):
    url = "https://itunes.apple.com/search"
    params = {
        "term": keyword,
        "country": country,
        "entity": "software",
        "limit": limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error: Request failed - {e}")
        sys.exit(1)
        
    try:
        data = response.json()
    except ValueError:
        print("Error: Invalid response from server (not JSON).")
        sys.exit(1)
        
    return data.get("results", [])

def main():
    if len(sys.argv) < 3:
        print("Usage: python search.py <keyword> <country>")
        print("Example: python search.py \"flashcards\" us")
        sys.exit(1)
        
    keyword = sys.argv[1]
    country = sys.argv[2]
    
    print(f"Search: {keyword}")
    print(f"Country: {country.upper()}\n")
    
    results = search_app_store(keyword, country, limit=50)
    
    if not results:
        print("No results found.")
        return
        
    for index, result in enumerate(results, start=1):
        app_name = result.get("trackName", "Unknown App")
        developer = result.get("artistName", "Unknown Developer")
        app_id = result.get("trackId", "Unknown ID")
        
        print(f"#{index} {app_name}")
        print(f"   App ID: {app_id}")
        print(f"   Developer: {developer}\n")

if __name__ == "__main__":
    main()
