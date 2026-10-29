import re
import json

with open("trendshift_sample.html", "r", encoding="utf-8") as f:
    html = f.read()

# Let's split by repository links or cards
# Look for blocks containing <a href="/repositories/...
chunks = html.split('href="/repositories/')
print(f"Total chunks: {len(chunks)}")

repo_list = []
for c in chunks[1:]:
    # First part is repo ID: 1234"
    match_id = re.match(r'^(\d+)"', c)
    if not match_id:
        continue
    repo_id = match_id.group(1)
    
    # Extract repo full name: like user/repo
    name_match = re.search(r'([a-zA-Z0-9_\-\.]+/[a-zA-Z0-9_\-\.]+)', c[:500])
    repo_name = name_match.group(1) if name_match else None
    
    # Extract description
    # look for text after name
    desc_match = re.search(r'<p[^>]*>(.*?)</p>', c[:1500], re.DOTALL)
    desc = ""
    if desc_match:
        desc = re.sub(r'<[^>]+>', ' ', desc_match.group(1)).strip()
        desc = re.sub(r'\s+', ' ', desc)
        
    if repo_name and (repo_name, repo_id) not in [(r['name'], r['id']) for r in repo_list]:
        repo_list.append({
            "id": repo_id,
            "name": repo_name,
            "url": f"https://github.com/{repo_name}",
            "description": desc
        })

print(f"Unique repos extracted: {len(repo_list)}")
with open("extracted_repos.json", "w", encoding="utf-8") as out:
    json.dump(repo_list, out, indent=2, ensure_ascii=False)

for r in repo_list:
    print(f"[{r['id']}] {r['name']}: {r['description'][:80]}")
