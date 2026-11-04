#!/usr/bin/env python3
"""
Omni-Kernel v4.1: Workspace Virtualization Engine (Assimilator - Hardened)
Automatically discovers and assimilates local skills, rules, and conventions from ANY workspace.
Completely non-destructive and read-only on the target repository.
Equipped with AssimilatorGuard (Zero-Trust Sanitizer) to block Indirect Prompt Injections (IPI).
Remediated against VULN-007 (symlink traversal) and VULN-009 (memory/file size bounds).
"""

import os
import sys
import glob
import json
import time
import hashlib

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from indexer import parse_frontmatter, extract_tokens
from workspace_sanitizer import AssimilatorGuard, is_trusted_workspace

# Upper bound limits to defend against resource exhaustion DoS (VULN-009)
MAX_WORKSPACE_READ = 64 * 1024       # 64 KiB max per skill/rule file
MAX_WORKSPACE_SKILLS = 50            # Max local skills scanned
MAX_WORKSPACE_RULES = 100            # Max local rules scanned


def get_workspace_hash(workspace_dir: str) -> str:
    """Generates a stable MD5 identifier for a workspace path."""
    return hashlib.md5(os.path.abspath(workspace_dir).lower().encode("utf-8")).hexdigest()[:12]


def is_safe_workspace_file(file_path: str, workspace_dir: str) -> bool:
    """
    Verifies that file_path is a regular file, is NOT a symlink, and strictly resides
    inside the canonical workspace directory tree (VULN-007).
    """
    if not file_path or not os.path.isfile(file_path):
        return False
    if os.path.islink(file_path):
        return False
    try:
        ws_real = os.path.normcase(os.path.realpath(workspace_dir))
        f_real = os.path.normcase(os.path.realpath(file_path))
        return f_real.startswith(ws_real + os.sep) or f_real == ws_real
    except Exception:
        return False


def find_workspace_skills(workspace_dir: str, is_trusted: bool = False, blocked_list: list = None) -> list:
    """Scans for local skill definitions in standard agent folders with IPI guard and symlink containment."""
    discovered = []
    if not workspace_dir or not os.path.exists(workspace_dir):
        return discovered

    search_patterns = [
        os.path.normpath(os.path.join(workspace_dir, ".agents", "skills", "*", "SKILL.md")),
        os.path.normpath(os.path.join(workspace_dir, ".gemini", "skills", "*", "SKILL.md")),
        os.path.normpath(os.path.join(workspace_dir, "skills", "*", "SKILL.md")),
        os.path.normpath(os.path.join(workspace_dir, ".specify", "skills", "*", "SKILL.md")),
    ]

    seen_paths = set()
    for pattern in search_patterns:
        for skill_file in glob.glob(pattern):
            if len(discovered) >= MAX_WORKSPACE_SKILLS:
                break

            norm_path = os.path.normpath(skill_file)
            if norm_path in seen_paths:
                continue
            seen_paths.add(norm_path)

            # VULN-007: Reject symlinks and paths escaping workspace root
            if not is_safe_workspace_file(norm_path, workspace_dir):
                continue

            try:
                if os.path.getsize(norm_path) > MAX_WORKSPACE_READ:
                    continue

                with open(norm_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(MAX_WORKSPACE_READ)

                # Zero-Trust Check for Untrusted Workspaces
                if not is_trusted:
                    is_safe, violations = AssimilatorGuard.scan_rules(content, norm_path)
                    if not is_safe:
                        skill_name = os.path.basename(os.path.dirname(norm_path))
                        print(f"⚠️ [Assimilator] BLOCKED SKILL '{skill_name}': {violations}", file=sys.stderr)
                        if blocked_list is not None:
                            blocked_list.append({"file": norm_path, "type": "skill", "name": skill_name, "violations": violations})
                        continue

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
                    "quality_score": 95,
                    "mtime": int(os.path.getmtime(norm_path)),
                    "tokens": tokens,
                })
            except Exception:
                pass

    return discovered


def find_workspace_rules(workspace_dir: str, is_trusted: bool = False, blocked_list: list = None) -> list:
    """Scans and extracts local rules with IPI guard, symlink containment, and bounded reading."""
    rules = []
    if not workspace_dir or not os.path.exists(workspace_dir):
        return rules

    seen_paths = set()
    rule_candidates = [
        ("GEMINI.md", os.path.normpath(os.path.join(workspace_dir, "GEMINI.md"))),
        ("CLAUDE.md", os.path.normpath(os.path.join(workspace_dir, "CLAUDE.md"))),
        ("AGENTS.md", os.path.normpath(os.path.join(workspace_dir, "AGENTS.md"))),
        (".cursorrules", os.path.normpath(os.path.join(workspace_dir, ".cursorrules"))),
        ("rules/AGENTS.md", os.path.normpath(os.path.join(workspace_dir, "rules", "AGENTS.md"))),
        (".gemini/GEMINI.md", os.path.normpath(os.path.join(workspace_dir, ".gemini", "GEMINI.md"))),
        (".gemini/AGENTS.md", os.path.normpath(os.path.join(workspace_dir, ".gemini", "AGENTS.md"))),
        (".specify/constitution.md", os.path.normpath(os.path.join(workspace_dir, ".specify", "constitution.md"))),
        (".specify/memory/constitution.md", os.path.normpath(os.path.join(workspace_dir, ".specify", "memory", "constitution.md"))),
        ("constitution.md", os.path.normpath(os.path.join(workspace_dir, "constitution.md"))),
    ]

    for label, path in rule_candidates:
        if len(rules) >= MAX_WORKSPACE_RULES:
            break
        if not is_safe_workspace_file(path, workspace_dir):
            continue

        norm = os.path.normpath(path)
        if norm in seen_paths:
            continue
        seen_paths.add(norm)
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(4000)

            if not is_trusted:
                is_safe, violations = AssimilatorGuard.scan_rules(content, label)
                if not is_safe:
                    print(f"⚠️ [Assimilator] BLOCKED RULE '{label}': {violations}", file=sys.stderr)
                    if blocked_list is not None:
                        blocked_list.append({"file": norm, "type": "rule", "source": label, "violations": violations})
                    continue

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
        os.path.normpath(os.path.join(workspace_dir, ".specify", "*.md")),
        os.path.normpath(os.path.join(workspace_dir, "specs", "*", "*.md")),
    ]
    for pattern in dir_patterns:
        for r_file in glob.glob(pattern):
            if len(rules) >= MAX_WORKSPACE_RULES:
                break
            if not is_safe_workspace_file(r_file, workspace_dir):
                continue

            norm = os.path.normpath(r_file)
            if norm in seen_paths:
                continue
            seen_paths.add(norm)
            try:
                rel_name = os.path.relpath(r_file, workspace_dir).replace("\\", "/")
                with open(r_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(2000)

                if not is_trusted:
                    is_safe, violations = AssimilatorGuard.scan_rules(content, rel_name)
                    if not is_safe:
                        print(f"⚠️ [Assimilator] BLOCKED RULE '{rel_name}': {violations}", file=sys.stderr)
                        if blocked_list is not None:
                            blocked_list.append({"file": norm, "type": "rule", "source": rel_name, "violations": violations})
                        continue

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
    """Extracts all workspace-level skills and rules non-destructively, guarded by AssimilatorGuard."""
    start = time.time()
    is_trusted = is_trusted_workspace(workspace_dir)
    blocked = []
    skills = find_workspace_skills(workspace_dir, is_trusted=is_trusted, blocked_list=blocked)
    rules = find_workspace_rules(workspace_dir, is_trusted=is_trusted, blocked_list=blocked)
    elapsed = (time.time() - start) * 1000

    return {
        "workspace_dir": os.path.abspath(workspace_dir).replace("\\", "/"),
        "workspace_hash": get_workspace_hash(workspace_dir),
        "is_trusted": is_trusted,
        "skills_count": len(skills),
        "rules_count": len(rules),
        "blocked_count": len(blocked),
        "blocked": blocked,
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
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
