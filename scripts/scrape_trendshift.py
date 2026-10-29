import urllib.request
import re
import json

req = urllib.request.Request(
    'https://trendshift.io/',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read().decode('utf-8', errors='ignore')
        print(f"Status: {resp.status}, Content Length: {len(content)}")
        
        # Save sample for inspection
        with open("trendshift_sample.html", "w", encoding="utf-8") as f:
            f.write(content)
            
        # Extract links
        repo_links = re.findall(r'href=["\'](/repositories/[0-9]+)["\']', content)
        print("Internal repository IDs found:", len(repo_links))
        
        # Also look for repo titles or github names
        titles = re.findall(r'<h[234][^>]*>(.*?)</h[234]>', content, re.DOTALL)
        print("Headings found:", len(titles))
        for t in titles[:20]:
            clean = re.sub(r'<[^>]+>', '', t).strip()
            if clean:
                print(" -", clean)

except Exception as e:
    print(f"Error fetching Trendshift: {e}")
