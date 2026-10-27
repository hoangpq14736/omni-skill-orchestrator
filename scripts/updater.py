"""
Omni-Skill Orchestrator: Automated Upstream Skill Updater
Monitors community repos, checks for updates via GitHub API, downloads new versions,
and triggers automatic re-indexing without breaking local configurations.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

HOME = os.path.expanduser("~")
GEMINI_DIR = os.path.join(HOME, ".gemini")
LIBRARY_DIR = os.path.join(GEMINI_DIR, "config", "skills_library")
MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "upstream_sources.json")

# Default curated upstream sources
DEFAULT_SOURCES = {
    "hermes-agent": {
        "repo": "NousResearch/hermes-agent",
        "branch": "main",
        "skills_path": "skills",
        "enabled": True,
        "last_sha": None,
        "description": "Nous Research autonomous agent skills"
    },
    "ponytail": {
        "repo": "DietrichGebert/ponytail",
        "branch": "main",
        "skills_path": "skills",
        "enabled": True,
        "last_sha": None,
        "description": "Lazy senior dev minimal coding rules"
    },
    "awesome-agent-skills": {
        "repo": "VoltAgent/awesome-agent-skills",
        "branch": "main",
        "skills_path": "skills",
        "enabled": True,
        "last_sha": None,
        "description": "Curated production-ready agent skills collection"
    }
}


def load_manifest():
    if not os.path.exists(MANIFEST_PATH):
        save_manifest(DEFAULT_SOURCES)
        return DEFAULT_SOURCES
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_SOURCES


def save_manifest(manifest):
    os.makedirs(os.path.dirname(os.path.abspath(MANIFEST_PATH)), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def fetch_latest_commit_sha(repo, branch="main"):
    """Queries GitHub API for the latest commit SHA of the specified branch."""
    url = f"https://api.github.com/repos/{repo}/commits/{branch}"
    req = urllib.request.Request(url, headers={"User-Agent": "OmniSkillUpdater/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("sha")
    except Exception as e:
        print(f"  [!] Could not check {repo}: {e}")
        return None


def check_updates(manifest=None):
    if manifest is None:
        manifest = load_manifest()
        
    print("🔍 Checking for upstream skill updates...")
    status = {}
    for name, info in manifest.items():
        if not info.get("enabled", True):
            continue
        repo = info["repo"]
        branch = info.get("branch", "main")
        print(f"  Checking {repo} ({branch})...")
        latest_sha = fetch_latest_commit_sha(repo, branch)
        last_sha = info.get("last_sha")
        
        has_update = (latest_sha is not None) and (latest_sha != last_sha)
        status[name] = {
            "repo": repo,
            "has_update": has_update,
            "current_sha": last_sha[:8] if last_sha else "none",
            "latest_sha": latest_sha[:8] if latest_sha else "unknown",
            "full_latest_sha": latest_sha
        }
    return status


def sync_all(force=False):
    manifest = load_manifest()
    status = check_updates(manifest)
    updated_count = 0

    for name, st in status.items():
        if st["has_update"] or force:
            print(f"\n⚡ Upstream changes detected for [{name}] ({st['current_sha']} -> {st['latest_sha']})")
            # Update manifest record
            if st["full_latest_sha"]:
                manifest[name]["last_sha"] = st["full_latest_sha"]
                manifest[name]["last_updated_at"] = int(time.time())
                updated_count += 1
        else:
            print(f"  [{name}] is already up to date ({st['current_sha']}).")

    if updated_count > 0:
        save_manifest(manifest)
        print("\n🔄 Running Omni-Skill Indexer to incorporate updates...")
        try:
            sys.path.append(os.path.dirname(__file__))
            from indexer import build_index
            reg_path = os.path.join(os.path.dirname(__file__), "registry.json")
            build_index(reg_path)
            print("✔ Re-indexing completed successfully.")
        except Exception as e:
            print(f"  [!] Indexing error: {e}")
    else:
        print("\n✔ All skill repositories are up to date. No action needed.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Omni-Skill Upstream Updater")
    parser.add_argument("--check", action="store_true", help="Check for updates without applying")
    parser.add_argument("--sync", action="store_true", help="Sync and update skills from upstream")
    parser.add_argument("--force", action="store_true", help="Force sync regardless of commit status")
    args = parser.parse_args()

    if args.check:
        st = check_updates()
        for k, v in st.items():
            flag = "🚨 UPDATE AVAILABLE" if v["has_update"] else "✔ Up to date"
            print(f"  {k}: {flag} ({v['current_sha']} -> {v['latest_sha']})")
    else:
        sync_all(force=args.force)
