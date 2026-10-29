#!/usr/bin/env python3
"""
Omni-Kernel v3.0: Workspace Virtualization Engine (Assimilator)
Automatically discovers and assimilates local skills, rules, and conventions from ANY workspace.
Completely non-destructive and read-only on the target repository.
Supported formats:
- Skills: .agents/skills/*/SKILL.md, .gemini/skills/*/SKILL.md, skills/*/SKILL.md
- Rules: GEMINI.md, CLAUDE.md, AGENTS.md, .cursorrules, .cursor/rules/*.mdc, .agents/rules/*.md
"""

import os
import sys
import glob
import json
import time
import hashlib

# Ensure scripts directory is on sys.path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from indexer import parse_frontmatter, extract_tokens


def get_workspace_hash(workspace_dir: str) -> str:
    """Generates a stable MD5 identifier for a workspace path."""
    return hashlib.md5(os.path.abspath(workspace_dir).lower().encode("utf-8")).hexdigest()[:12]


def find_workspace_skills(workspace_dir: str) -> list:
    """Scans for local skill definitions in standard agent folders."""
    discovered = []
    if not workspace_dir or not os.path.exists(workspace_dir):
        return discovered

    search_patterns = [
        os.path.normpath(os.path.join(workspace_dir, ".agents", "skills", "*", "SKILL.md")),
        os.path.normpath(os.path.join(workspace_dir, ".gemini", "skills", "*", "SKILL.md")),
        os.path.normpath(os.path.join(workspace_dir, "skills", "*", "SKILL.md")),
    ]

    seen_paths = set()
    for pattern in search_patterns:
        for skill_file in glob.glob(pattern):
            norm_path = os.path.normpath(skill_file)
            if norm_path in seen_paths:
                continue
            seen_paths.add(norm_path)

            try:
                with open(norm_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                fm, _ = parse_frontmatter(content)
                name = fm.get("name") or os.path.basename(os.path.dirname(norm_path))
                desc = fm.get("description", "")
                version = fm.get("version", "1.0.0")
                tokens = list(set(extract_tokens(name) + extract_tokens(desc)))

                discovered.append({
                    "id": f"workspace:{name}",
                    "name": name,
                    "source_type": "workspace",
                    "plugin_name": None,
                    "path": norm_path.replace("\\", "/"),
                    "description": desc,
                    "version": version,
                    "quality_score": 95,  # Workspace local skills get high preference
                    "mtime": int(os.path.getmtime(norm_path)),
                    "tokens": tokens,
                })
            except Exception:
                pass

    return discovered


def find_workspace_rules(workspace_dir: str) -> list:
    """Scans and extracts local rules from Cursor, Claude, Gemini, or Antigravity files."""
    rules = []
    if not workspace_dir or not os.path.exists(workspace_dir):
        return rules

    seen_paths = set()
    rule_candidates = [
        # Root markdown conventions
        ("GEMINI.md", os.path.normpath(os.path.join(workspace_dir, "GEMINI.md"))),
        ("CLAUDE.md", os.path.normpath(os.path.join(workspace_dir, "CLAUDE.md"))),
        ("AGENTS.md", os.path.normpath(os.path.join(workspace_dir, "AGENTS.md"))),
        (".cursorrules", os.path.normpath(os.path.join(workspace_dir, ".cursorrules"))),
        ("rules/AGENTS.md", os.path.normpath(os.path.join(workspace_dir, "rules", "AGENTS.md"))),
        (".gemini/GEMINI.md", os.path.normpath(os.path.join(workspace_dir, ".gemini", "GEMINI.md"))),
        (".gemini/AGENTS.md", os.path.normpath(os.path.join(workspace_dir, ".gemini", "AGENTS.md"))),
    ]

    for label, path in rule_candidates:
        if os.path.isfile(path):
            norm = os.path.normpath(path)
            if norm in seen_paths:
                continue
            seen_paths.add(norm)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(4000)  # Read first 4KB
                first_lines = [line.strip("# -*").strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("```")][:3]
                summary = " | ".join(first_lines) if first_lines else "Custom repository rules"
                rules.append({
                    "source": label,
                    "path": norm.replace("\\", "/"),
                    "summary": summary[:160],
                    "content_preview": content[:500]
                })
            except Exception:
                pass

    # Directory-based rules: .cursor/rules/*.mdc, .agents/rules/*.md, rules/*.md
    dir_patterns = [
        os.path.normpath(os.path.join(workspace_dir, ".cursor", "rules", "*.md*")),
        os.path.normpath(os.path.join(workspace_dir, ".agents", "rules", "*.md")),
        os.path.normpath(os.path.join(workspace_dir, ".gemini", "rules", "*.md")),
        os.path.normpath(os.path.join(workspace_dir, "rules", "*.md")),
    ]
    for pattern in dir_patterns:
        for r_file in glob.glob(pattern):
            if os.path.isfile(r_file):
                norm = os.path.normpath(r_file)
                if norm in seen_paths:
                    continue
                seen_paths.add(norm)
                try:
                    rel_name = os.path.relpath(r_file, workspace_dir).replace("\\", "/")
                    with open(r_file, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(2000)
                    first_lines = [line.strip("# -*").strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("```")][:2]
                    summary = " | ".join(first_lines) if first_lines else "Directory rule"
                    rules.append({
                        "source": rel_name,
                        "path": norm.replace("\\", "/"),
                        "summary": summary[:160],
                        "content_preview": content[:400]
                    })
                except Exception:
                    pass

    return rules


def assimilate_workspace(workspace_dir: str) -> dict:
    """Extracts all workspace-level skills and rules non-destructively."""
    start = time.time()
    skills = find_workspace_skills(workspace_dir)
    rules = find_workspace_rules(workspace_dir)
    elapsed = (time.time() - start) * 1000

    return {
        "workspace_dir": os.path.abspath(workspace_dir).replace("\\", "/"),
        "workspace_hash": get_workspace_hash(workspace_dir),
        "skills_count": len(skills),
        "rules_count": len(rules),
        "skills": skills,
        "rules": rules,
        "elapsed_ms": round(elapsed, 2)
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Omni-Kernel Workspace Assimilator")
    parser.add_argument("--workspace", default=os.getcwd(), help="Target workspace directory to assimilate")
    parser.add_argument("--json", action="store_true", help="Output full JSON")
    args = parser.parse_args()

    result = assimilate_workspace(args.workspace)
    if args.json or True:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
