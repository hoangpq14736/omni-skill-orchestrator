"""
Omni-Skill Orchestrator: Indexing Engine
Zero-dependency, high-speed scanner and indexer for all skill sources.
"""

import os
import re
import json
import time

HOME = os.path.expanduser("~")
GEMINI_DIR = os.path.join(HOME, ".gemini")

SOURCES = {
    "plugin": os.path.join(GEMINI_DIR, "config", "plugins"),
    "user_active": os.path.join(GEMINI_DIR, "config", "skills"),
    "library": os.path.join(GEMINI_DIR, "config", "skills_library"),
    "builtin": os.path.join(GEMINI_DIR, "antigravity", "builtin", "skills"),
}


def parse_frontmatter(content):
    meta = {}
    body = content
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_meta = parts[1]
            body = parts[2]
            current_key = None
            current_val = []
            
            for line in raw_meta.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                # If unindented key
                if not line.startswith(" ") and not line.startswith("\t") and ":" in line:
                    if current_key:
                        meta[current_key] = " ".join(current_val).strip()
                    k, v = line.split(":", 1)
                    current_key = k.strip()
                    v_str = v.strip().strip("\"'")
                    if v_str in [">-", "|", ">", "|-", ""]:
                        current_val = []
                    else:
                        current_val = [v_str]
                elif current_key and (line.startswith(" ") or line.startswith("\t")):
                    current_val.append(stripped.strip("\"'"))
            
            if current_key:
                meta[current_key] = " ".join(current_val).strip()
                
    return meta, body


def extract_version_clues(text, plugin_version=None):
    if plugin_version:
        return plugin_version
    # Search for version markers like v1.2, Swift 6.2, React 19, Python 3.12
    v_match = re.search(r'\b(?:v|version\s*)(\d+\.\d+(?:\.\d+)?)\b', text, re.IGNORECASE)
    if v_match:
        return v_match.group(1)
    tech_v = re.search(r'\b(react|swift|python|vue|angular|node|go|rust|php|java)\s*(\d+(?:\.\d+)?)\b', text, re.IGNORECASE)
    if tech_v:
        return f"{tech_v.group(1).lower()}-{tech_v.group(2)}"
    return "1.0.0"


def calculate_quality_score(content, meta):
    score = 50
    desc = meta.get("description", "")
    if desc:
        score += 15
    if len(desc) > 60:
        score += 10
    if "## When to Activate" in content or "## When to Use" in content or "## Triggers" in content:
        score += 15
    if "```" in content: # Contains code samples / examples
        score += 10
    return min(score, 100)


def extract_tokens(text):
    """Extracts both individual words and hyphenated compounds."""
    tokens = set()
    # Individual words
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    for w in words:
        if len(w) >= 2:
            tokens.add(w)
    # Hyphenated compounds
    compounds = re.findall(r'[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)+', text.lower())
    for c in compounds:
        tokens.add(c)
    return list(tokens)


def safe_listdir(path):
    """Safely lists directory entries without crashing on PermissionError or OS locks."""
    if not path or not os.path.exists(path):
        return []
    try:
        return os.listdir(path)
    except Exception:
        return []


def scan_all_skills(extra_workspace_paths=None):
    skills = []
    
    # 1. Scan Plugins
    plugin_root = SOURCES["plugin"]
    if os.path.exists(plugin_root):
        for plugin_name in safe_listdir(plugin_root):
            pdir = os.path.join(plugin_root, plugin_name)
            if not os.path.isdir(pdir):
                continue
            
            p_ver = None
            pjson_path = os.path.join(pdir, "plugin.json")
            if os.path.exists(pjson_path):
                try:
                    with open(pjson_path, "r", encoding="utf-8", errors="ignore") as f:
                        pj = json.load(f)
                        p_ver = pj.get("version")
                except Exception:
                    pass

            skills_dir = os.path.join(pdir, "skills")
            if os.path.exists(skills_dir):
                for item in safe_listdir(skills_dir):
                    sdir = os.path.join(skills_dir, item)
                    sm_file = os.path.join(sdir, "SKILL.md") if os.path.isdir(sdir) else (sdir if item == "SKILL.md" else None)
                    if sm_file and os.path.exists(sm_file):
                        skill_name = item if os.path.isdir(sdir) else plugin_name
                        skills.append(_parse_skill_file(sm_file, skill_name, "plugin", plugin_name, p_ver))

    # 2. Scan User Active Skills
    active_root = SOURCES["user_active"]
    if os.path.exists(active_root):
        for item in safe_listdir(active_root):
            sdir = os.path.join(active_root, item)
            sm_file = os.path.join(sdir, "SKILL.md")
            if os.path.exists(sm_file):
                skills.append(_parse_skill_file(sm_file, item, "user_active"))

    # 3. Scan Offline Library
    lib_root = SOURCES["library"]
    if os.path.exists(lib_root):
        for item in safe_listdir(lib_root):
            sdir = os.path.join(lib_root, item)
            sm_file = os.path.join(sdir, "SKILL.md")
            if os.path.exists(sm_file):
                skills.append(_parse_skill_file(sm_file, item, "library"))

    # 4. Scan Builtin
    builtin_root = SOURCES["builtin"]
    if os.path.exists(builtin_root):
        for item in safe_listdir(builtin_root):
            sdir = os.path.join(builtin_root, item)
            sm_file = os.path.join(sdir, "SKILL.md")
            if os.path.exists(sm_file):
                skills.append(_parse_skill_file(sm_file, item, "builtin"))

    # 5. Scan Workspace skills
    if extra_workspace_paths:
        for ws in extra_workspace_paths:
            for rel in [".agents/skills", ".gemini/skills", "skills"]:
                ws_skills = os.path.join(ws, rel)
                if os.path.exists(ws_skills):
                    for item in safe_listdir(ws_skills):
                        sdir = os.path.join(ws_skills, item)
                        sm_file = os.path.join(sdir, "SKILL.md")
                        if os.path.exists(sm_file):
                            skills.append(_parse_skill_file(sm_file, item, "workspace"))

    return skills


def _parse_skill_file(file_path, default_name, source_type, plugin_name=None, plugin_version=None):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception:
        content = ""

    meta, body = parse_frontmatter(content)
    skill_name = meta.get("name") or default_name
    desc = meta.get("description") or ""
    
    # Extract rich token set from name, description, and top headers
    tokens = extract_tokens(skill_name + " " + desc + " " + (plugin_name or ""))
    version = extract_version_clues(desc + " " + skill_name, plugin_version)
    q_score = calculate_quality_score(content, meta)
    mtime = int(os.path.getmtime(file_path)) if os.path.exists(file_path) else 0

    return {
        "id": f"{source_type}:{skill_name}",
        "name": skill_name,
        "source_type": source_type,
        "plugin_name": plugin_name,
        "path": os.path.abspath(file_path).replace("\\", "/"),
        "description": desc,
        "version": version,
        "quality_score": q_score,
        "mtime": mtime,
        "tokens": tokens,
    }


def is_registry_stale(registry, sources=SOURCES):
    """Checks in <1ms if any skill directory was modified since last index."""
    gen_time = registry.get("generated_at", 0)
    if not gen_time:
        return True
    for s_path in sources.values():
        if os.path.exists(s_path):
            if os.path.getmtime(s_path) > gen_time:
                return True
            try:
                with os.scandir(s_path) as it:
                    for entry in it:
                        if entry.stat().st_mtime > gen_time:
                            return True
            except Exception:
                pass
    return False


def build_index(output_file=None):
    start = time.time()
    skills = scan_all_skills()
    
    token_index = {}
    for idx, s in enumerate(skills):
        for t in s["tokens"]:
            if t not in token_index:
                token_index[t] = []
            token_index[t].append(idx)

    registry = {
        "generated_at": int(time.time()),
        "total_skills": len(skills),
        "sources_scanned": SOURCES,
        "skills": skills,
        "token_index": token_index
    }

    if output_file:
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)

    duration = time.time() - start
    print(f"Indexed {len(skills)} skills in {duration:.2f}s -> {output_file or 'in-memory'}")
    return registry


if __name__ == "__main__":
    out = os.path.join(os.path.dirname(__file__), "registry.json")
    build_index(out)
