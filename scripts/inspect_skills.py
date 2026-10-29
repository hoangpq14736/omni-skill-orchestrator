import json
import urllib.request
import urllib.error

candidates = [
    "pbakaus/impeccable",
    "Leonxlnx/taste-skill",
    "google/elephant-goldfish-model",
    "obra/superpowers",
    "morluto/rea",
    "JimLiu/baoyu-design"
]

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/vnd.github.v3+json"
}

for repo in candidates:
    print(f"\n=================== {repo} ===================")
    api_url = f"https://api.github.com/repos/{repo}/contents"
    req = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            contents = json.loads(resp.read().decode("utf-8"))
            files = [item["name"] for item in contents]
            print("Root files:", files[:15])
            
            # Check for skills directory or SKILL.md
            has_skill_md = "SKILL.md" in files
            has_skills_dir = "skills" in files or ".agents" in files or "rules" in files
            print(f"Has SKILL.md: {has_skill_md}, Has skills/rules dir: {has_skills_dir}")
            
            # If skills directory exists, list them
            if "skills" in files:
                skills_url = f"https://api.github.com/repos/{repo}/contents/skills"
                req_skills = urllib.request.Request(skills_url, headers=headers)
                with urllib.request.urlopen(req_skills, timeout=10) as s_resp:
                    s_contents = json.loads(s_resp.read().decode("utf-8"))
                    print("Skills subfolders:", [x["name"] for x in s_contents])
    except Exception as e:
        print(f"Error checking {repo}: {e}")
