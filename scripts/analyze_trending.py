import json
import urllib.request
import urllib.error
import time

with open("extracted_repos.json", "r", encoding="utf-8") as f:
    repos = json.load(f)

results = []
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/vnd.github.v3+json"
}

for i, r in enumerate(repos):
    name = r["name"]
    api_url = f"https://api.github.com/repos/{name}"
    print(f"[{i+1}/{len(repos)}] Fetching {name}...")
    req = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            desc = data.get("description") or ""
            topics = data.get("topics") or []
            stars = data.get("stargazers_count", 0)
            lang = data.get("language") or ""
            default_branch = data.get("default_branch", "main")
            
            # Check keywords for Skill, Rules, MCP
            text_to_check = f"{name} {desc} {' '.join(topics)}".lower()
            is_relevant = any(k in text_to_check for k in ["skill", "skills", "rule", "rules", "mcp", "model-context-protocol", "cursorrules", "agent"])
            
            results.append({
                "name": name,
                "url": f"https://github.com/{name}",
                "description": desc,
                "topics": topics,
                "stars": stars,
                "language": lang,
                "default_branch": default_branch,
                "is_relevant": is_relevant
            })
    except urllib.error.HTTPError as e:
        print(f"  HTTP error {e.code} for {name}")
        results.append({
            "name": name,
            "url": f"https://github.com/{name}",
            "description": r.get("description", ""),
            "topics": [],
            "stars": 0,
            "language": "",
            "is_relevant": False
        })
    except Exception as e:
        print(f"  Error {e} for {name}")
        results.append({
            "name": name,
            "url": f"https://github.com/{name}",
            "description": r.get("description", ""),
            "topics": [],
            "stars": 0,
            "language": "",
            "is_relevant": False
        })
    time.sleep(0.5)  # Avoid rate limiting

with open("analyzed_repos.json", "w", encoding="utf-8") as out:
    json.dump(results, out, indent=2, ensure_ascii=False)

print("\n--- RELEVANT CANDIDATES (Skills / Rules / MCP / Agents) ---")
for r in results:
    if r["is_relevant"]:
        print(f"⭐ {r['name']} ({r['stars']} stars): {r['description']}")
        print(f"   Topics: {r['topics']}")

print("\n--- UNRELATED CANDIDATES ---")
for r in results:
    if not r["is_relevant"]:
        print(f"• {r['name']}: {r['description']}")
