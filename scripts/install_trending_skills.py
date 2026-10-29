import os
import sys
import json
import urllib.request

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from indexer import build_index, parse_frontmatter

LIBRARY_DIR = r"C:\Users\vuhuu\.gemini\config\skills_library"
os.makedirs(LIBRARY_DIR, exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/vnd.github.v3+json"}

SKILLS_TO_INSTALL = [
    # obra/superpowers (Core Agentic Engineering Skills)
    {
        "repo": "obra/superpowers",
        "branch": "main",
        "remote_path": "skills/subagent-driven-development/SKILL.md",
        "dest_name": "subagent-driven-development",
        "category": "Multi-Agent Orchestration",
        "reason": "Framework cho phép chia nhỏ kế hoạch, điều phối subagent độc lập và review tự động từng task."
    },
    {
        "repo": "obra/superpowers",
        "branch": "main",
        "remote_path": "skills/systematic-debugging/SKILL.md",
        "dest_name": "systematic-debugging",
        "category": "Root Cause Debugging",
        "reason": "Quy trình cô lập nguyên nhân gốc rễ trước khi sửa code, loại bỏ tư duy 'chữa triệu chứng'."
    },
    {
        "repo": "obra/superpowers",
        "branch": "main",
        "remote_path": "skills/verification-before-completion/SKILL.md",
        "dest_name": "verification-before-completion",
        "category": "Quality Assurance",
        "reason": "Checklist nghiệm thu thực tế trước khi tuyên bố hoàn thành, kiểm tra log, test và side-effects."
    },
    {
        "repo": "obra/superpowers",
        "branch": "main",
        "remote_path": "skills/dispatching-parallel-agents/SKILL.md",
        "dest_name": "dispatching-parallel-agents",
        "category": "Swarm Parallelism",
        "reason": "Chiến lược phân tách công việc và điều phối nhiều subagent chạy song song không xung đột."
    },
    # Leonxlnx/taste-skill (Anti-AI Slop UI/UX)
    {
        "repo": "Leonxlnx/taste-skill",
        "branch": "main",
        "remote_path": "skills/taste-skill/SKILL.md",
        "dest_name": "taste-skill",
        "category": "Frontend Anti-Slop UI",
        "reason": "Hệ thống tiêu chuẩn thẩm mỹ UI/UX thực tế từ 247 gallery đoạt giải, chống tình trạng sinh code giao diện nhàm chán/AI slop."
    },
    # google/elephant-goldfish-model (Spec-Driven Architecture Review)
    {
        "repo": "google/elephant-goldfish-model",
        "branch": "main",
        "remote_path": "skills/egm-review/SKILL.md",
        "dest_name": "egm-review",
        "category": "Spec-Driven Review Protocol",
        "reason": "Giao thức 5 pha của Google để review tài liệu thiết kế kiến trúc và mã nguồn đa tác tử."
    }
]

installed_results = []

for item in SKILLS_TO_INSTALL:
    dest_dir = os.path.join(LIBRARY_DIR, item["dest_name"])
    os.makedirs(dest_dir, exist_ok=True)
    dest_file = os.path.join(dest_dir, "SKILL.md")
    
    url = f"https://raw.githubusercontent.com/{item['repo']}/{item['branch']}/{item['remote_path']}"
    print(f"Downloading {item['dest_name']} from {url}...")
    
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read().decode("utf-8")
            
        # Validate frontmatter
        meta, body = parse_frontmatter(content)
        name = meta.get("name") or item["dest_name"]
        desc = meta.get("description", "")
        
        # Save file
        with open(dest_file, "w", encoding="utf-8") as f:
            f.write(content)
            
        print(f"  ✅ Installed to {dest_file} (Name: {name}, Desc: {desc[:60]}...)")
        installed_results.append({
            "name": item["dest_name"],
            "repo": item["repo"],
            "category": item["category"],
            "reason": item["reason"],
            "file": dest_file,
            "status": "Installed"
        })
    except Exception as e:
        print(f"  ❌ Error installing {item['dest_name']}: {e}")
        installed_results.append({
            "name": item["dest_name"],
            "repo": item["repo"],
            "category": item["category"],
            "reason": item["reason"],
            "status": f"Failed: {e}"
        })

# Rebuild index
print("\nRebuilding Omni-Kernel virtual registry index...")
reg = build_index()
print(f"Registry updated: Total {len(reg.get('skills', []))} skills in index.")

with open("installed_trending_summary.json", "w", encoding="utf-8") as out:
    json.dump(installed_results, out, indent=2, ensure_ascii=False)
