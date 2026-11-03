#!/usr/bin/env python3
"""
Omni-Kernel v4.1: Internal Skill & Version Synchronizer
Autonomous Engine for detecting and auto-healing Version Drift across all
Omni-Kernel skills (spec-driven-development, omni-skill-orchestrator, skill-arbiter),
Constitution invariants, and virtual registry index.

Usage:
    python scripts/kernel_sync.py --check
    python scripts/kernel_sync.py --fix
    python scripts/kernel_sync.py --target-version 4.1.0
"""

import argparse
import json
import os
import re
import sys
import time

HOME = os.path.expanduser("~")
GEMINI_DIR = os.path.join(HOME, ".gemini")
PLUGIN_DIR = os.path.join(GEMINI_DIR, "config", "plugins", "omni-skill-orchestrator")
LIBRARY_DIR = os.path.join(GEMINI_DIR, "config", "skills_library")
ACTIVE_SKILLS_DIR = os.path.join(GEMINI_DIR, "config", "skills")
WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Canonical core skills governed directly by Omni-Kernel
CORE_KERNEL_SKILLS = {
    "spec-driven-development",
    "omni-skill-orchestrator",
    "skill-arbiter"
}


def get_canonical_kernel_version(workspace=WORKSPACE_DIR) -> str:
    """Extracts the ratified Constitution version or plugin version as source of truth."""
    # 1. Try constitution.md
    constitution_path = os.path.join(workspace, ".specify", "constitution.md")
    if os.path.exists(constitution_path):
        try:
            with open(constitution_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                # Look for Version: X.Y.Z
                m = re.search(r'\bVersion\s*:\s*(\d+\.\d+\.\d+)', content, re.IGNORECASE)
                if m:
                    return m.group(1)
        except Exception:
            pass

    # 2. Try plugin.json
    pjson_path = os.path.join(PLUGIN_DIR, "plugin.json")
    if os.path.exists(pjson_path):
        try:
            with open(pjson_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
                if "version" in data:
                    return data["version"]
        except Exception:
            pass

    return "4.1.0"


def find_all_kernel_skill_files(workspace=WORKSPACE_DIR):
    """Finds all SKILL.md files for core kernel skills across plugin, workspace, and library."""
    found_files = {}

    search_roots = {
        "workspace": os.path.join(workspace, "skills"),
        "plugin": os.path.join(PLUGIN_DIR, "skills"),
        "library": LIBRARY_DIR,
        "active": ACTIVE_SKILLS_DIR
    }

    for scope, root in search_roots.items():
        if not os.path.exists(root):
            continue
        for root_dir, _, files in os.walk(root):
            for f in files:
                if f.lower() == "skill.md":
                    full_path = os.path.join(root_dir, f)
                    # Check parent folder name
                    skill_name = os.path.basename(os.path.dirname(full_path))
                    if skill_name in CORE_KERNEL_SKILLS:
                        if skill_name not in found_files:
                            found_files[skill_name] = []
                        found_files[skill_name].append({
                            "scope": scope,
                            "path": full_path,
                            "skill_name": skill_name
                        })

    return found_files


def extract_skill_version(content: str) -> str:
    """Extracts version from frontmatter metadata or text."""
    # Check frontmatter metadata.version
    m_meta = re.search(r'metadata:\s*\n(?:\s+.*\n)*?\s+version:\s*["\']?([0-9\.]+)["\']?', content)
    if m_meta:
        return m_meta.group(1)
    
    m_v = re.search(r'version:\s*["\']?([0-9\.]+)["\']?', content)
    if m_v:
        return m_v.group(1)
    return "unknown"


def audit_kernel_skills(target_version: str, workspace=WORKSPACE_DIR):
    """Audits all core kernel skills for version drift against target_version."""
    files_map = find_all_kernel_skill_files(workspace)
    report = []

    for skill_name, entries in sorted(files_map.items()):
        for entry in entries:
            p = entry["path"]
            scope = entry["scope"]
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                current_v = extract_skill_version(content)
                has_stale_text = any(stale in content for stale in ["Omni-Kernel v3.0", "Omni-Kernel v2.0", "Omni-Kernel Orchestrator v2.0"])
                
                is_drifted = (current_v != target_version) or has_stale_text
                report.append({
                    "skill_name": skill_name,
                    "scope": scope,
                    "path": p,
                    "current_version": current_v,
                    "target_version": target_version,
                    "is_drifted": is_drifted,
                    "has_stale_text": has_stale_text
                })
            except Exception as e:
                report.append({
                    "skill_name": skill_name,
                    "scope": scope,
                    "path": p,
                    "error": str(e)
                })

    return report


def sync_kernel_skills(target_version: str, workspace=WORKSPACE_DIR, auto_reindex=True):
    """Automatically fixes version drift across all core kernel skills and re-indexes."""
    report = audit_kernel_skills(target_version, workspace)
    fixed_count = 0

    major_minor = ".".join(target_version.split(".")[:2]) # e.g. 4.1

    for item in report:
        if not item.get("is_drifted"):
            continue

        p = item["path"]
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()

            # 1. Update frontmatter version
            if "version:" in content:
                content = re.sub(
                    r'(metadata:\s*\n(?:\s+.*\n)*?\s+version:\s*)["\']?[0-9\.]+["\']?',
                    rf'\g<1>{target_version}',
                    content
                )
                content = re.sub(
                    r'^(version:\s*)["\']?[0-9\.]+["\']?',
                    rf'\g<1>{target_version}',
                    content,
                    flags=re.MULTILINE
                )

            # 2. Update stale title / body references
            content = content.replace("Omni-Kernel v3.0", f"Omni-Kernel v{major_minor}")
            content = content.replace("Omni-Kernel v2.0", f"Omni-Kernel v{major_minor}")
            content = content.replace("Omni-Kernel Orchestrator v2.0", f"Omni-Kernel Orchestrator v{major_minor}")
            content = content.replace("Engine v3.0", f"Engine v{major_minor}")

            with open(p, "w", encoding="utf-8") as f:
                f.write(content)

            item["fixed"] = True
            fixed_count += 1
        except Exception as e:
            item["fix_error"] = str(e)

    # Reindex if requested and modifications were made
    if auto_reindex:
        try:
            indexer_path = os.path.join(PLUGIN_DIR, "scripts", "indexer.py")
            if not os.path.exists(indexer_path):
                indexer_path = os.path.join(workspace, "scripts", "indexer.py")
            
            if os.path.exists(indexer_path):
                sys.path.insert(0, os.path.dirname(indexer_path))
                import indexer
                reg_path = os.path.join(os.path.dirname(indexer_path), "registry.json")
                indexer.build_index(reg_path)
                print(f"✔ Re-indexing completed successfully into {reg_path}")
        except Exception as e:
            print(f"[!] Re-indexing warning: {e}", file=sys.stderr)

    return report, fixed_count


def main():
    parser = argparse.ArgumentParser(description="Omni-Kernel v4.1 Skill Version Alignment & Auto-Sync Engine")
    parser.add_argument("--check", action="store_true", help="Audit skills for version drift without modifying files")
    parser.add_argument("--fix", action="store_true", help="Auto-heal and synchronize all kernel skills to target version")
    parser.add_argument("--target-version", type=str, default=None, help="Target Omni-Kernel version (defaults to Constitution version)")
    parser.add_argument("--workspace", type=str, default=WORKSPACE_DIR, help="Workspace directory path")

    args = parser.parse_args()

    target_v = args.target_version or get_canonical_kernel_version(args.workspace)
    print(f"🧠 OMNI-KERNEL SKILL SYNCHRONIZER (Target Version: v{target_v})\n" + "=" * 65)

    if args.check or not args.fix:
        report = audit_kernel_skills(target_v, args.workspace)
        drift_count = sum(1 for r in report if r.get("is_drifted"))
        for r in report:
            status = "🚨 DRIFTED" if r.get("is_drifted") else "✔ ALIGNED"
            print(f"  [{r['scope'].upper():9}] {r['skill_name']} -> {r['current_version']} vs v{r['target_version']} [{status}]")
            if r.get("is_drifted"):
                print(f"             Path: {r['path']}")
        
        print("\n" + "-" * 65)
        print(f"Total skills audited: {len(report)} | Version Drifted: {drift_count}")
        if drift_count > 0 and not args.fix:
            print("💡 Run with --fix to automatically synchronize all skills and re-index.")
    else:
        print(f"⚡ Synchronizing all core skills to Omni-Kernel v{target_v}...")
        report, fixed_count = sync_kernel_skills(target_v, args.workspace, auto_reindex=True)
        for r in report:
            status = "✔ FIXED" if r.get("fixed") else ("✔ ALIGNED" if not r.get("is_drifted") else "❌ FAILED")
            print(f"  [{r['scope'].upper():9}] {r['skill_name']} ({r['current_version']} -> v{r['target_version']}) [{status}]")
        print("\n" + "=" * 65)
        print(f"Synchronization complete! {fixed_count} skill files updated and aligned.")


if __name__ == "__main__":
    main()
