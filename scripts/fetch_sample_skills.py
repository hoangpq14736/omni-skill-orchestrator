import urllib.request
import json

headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.v3+json"}

def fetch_skill(repo, skill_path):
    url = f"https://raw.githubusercontent.com/{repo}/main/{skill_path}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        # Try master
        url_master = f"https://raw.githubusercontent.com/{repo}/master/{skill_path}"
        try:
            req = urllib.request.Request(url_master, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as resp:
                return resp.read().decode("utf-8")
        except Exception:
            return f"Error: {e}"

# Check sample skills
samples = [
    ("google/elephant-goldfish-model", "skills/egm-review/SKILL.md"),
    ("google/elephant-goldfish-model", "skills/egm-draft/SKILL.md"),
    ("obra/superpowers", "skills/subagent-driven-development/SKILL.md"),
    ("obra/superpowers", "skills/systematic-debugging/SKILL.md"),
    ("Leonxlnx/taste-skill", "skills/taste-skill/SKILL.md"),
]

for repo, path in samples:
    print(f"\n--- {repo}: {path} ---")
    content = fetch_skill(repo, path)
    print(content[:300] + "...")
