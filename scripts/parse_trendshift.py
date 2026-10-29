import re
import json

with open("trendshift_sample.html", "r", encoding="utf-8") as f:
    html = f.read()

# Check for JSON data in script tags
scripts = re.findall(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
if scripts:
    data = json.loads(scripts[0])
    with open("trendshift_data.json", "w", encoding="utf-8") as out:
        json.dump(data, out, indent=2, ensure_ascii=False)
    print("Extracted __NEXT_DATA__ successfully!")
else:
    # Try any json in script
    json_scripts = re.findall(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', html, re.DOTALL)
    print(f"Found {len(json_scripts)} application/json script tags")
    for i, js in enumerate(json_scripts):
        try:
            parsed = json.loads(js)
            with open(f"trendshift_json_{i}.json", "w", encoding="utf-8") as out:
                json.dump(parsed, out, indent=2, ensure_ascii=False)
            print(f"Saved trendshift_json_{i}.json")
        except Exception:
            pass

# Fallback: regex parse HTML elements
# Look for repo card blocks
cards = re.findall(r'<a[^>]+href=["\'](/repositories/\d+)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
print(f"Found {len(cards)} repo anchor tags")
