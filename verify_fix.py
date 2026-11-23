
import os
from dotenv import load_dotenv
from core.item_checker import verify_industry_with_api

# Load env
load_dotenv()

def verify():
    print("Testing verify_industry_with_api for code 7468...")
    # Clear cache for this test to force API call (optional, but good for verification)
    # But since I just modified the code, the cache management is inside the function.
    # To be safe, I relies on the fact that if it was cached as "NOT_FOUND" previously, it might still be cached.
    # I should probably clear the cache file or force the function to ignore cache if possible.
    # The current implementation reads cache first. 
    # Let's verify what the previous cache state might be.
    # If the previous attempts failed, they might have cached "NOT_FOUND".
    
    # Let's inspect cache first
    import json
    from pathlib import Path
    
    cache_path = Path("cache/api_validation_cache.json")
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # If 7468 is in industries cache, remove it to force re-fetch with new logic
        if "industries" in data and "7468" in data["industries"]:
            print("Removing '7468' from cache to force API re-check with new logic...")
            del data["industries"]["7468"]
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    # Now verify
    results = verify_industry_with_api(industry_codes_4=["7468"])
    for res in results:
        print(f"Code: {res.get('입력값')}")
        print(f"Name: {res.get('매칭_업종명')}")
        print(f"Status: {res.get('status')}")
        print("-" * 20)

if __name__ == "__main__":
    verify()
