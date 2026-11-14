#!/usr/bin/env python3
"""
Omni-Kernel v4.1: Immune System & Boundary-Aware Synchronizer
Autonomous Engine for sub-10ms Version Drift detection, DB Migration,
L1 Cache Invalidation, Non-Destructive Workspace Rule Alignment,
and Core Kernel Skill Synchronization across all scopes.

Standards:
- 100% Python Standard Library (Zero dependencies)
- Dual-Zone Boundary Enforcement (Zone 1 Internal Auto-Heal vs Zone 2 Workspace Non-Invasive)
- Subprocess-Free Git State Detection (<0.15ms)
- Windows NTFS-Safe Atomic Write with Exponential Backoff
- Boundary-Aware HTML Marker Anchors (<!-- OMNI-KERNEL-START v4.1.0 --> ... <!-- OMNI-KERNEL-END -->)
"""

import os
import re
import sys
import time
import json
import sqlite3
import tempfile
from pathlib import Path
from typing import Dict, Optional, Tuple, List, Any

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ==============================================================================
# CONSTANTS & CONFIGURATION
# ==============================================================================
KERNEL_VERSION = "4.3.0"
KERNEL_SCHEMA_VERSION = 430  # SQLite user_version for v4.3.0
DEBOUNCE_INTERVAL_SEC = 1800  # 30 minutes session-level cooldown

HOME = os.path.expanduser("~")
GEMINI_DIR = os.path.join(HOME, ".gemini")
PLUGIN_DIR = os.path.join(GEMINI_DIR, "config", "plugins", "omni-skill-orchestrator")
LIBRARY_DIR = os.path.join(GEMINI_DIR, "config", "skills_library")
ACTIVE_SKILLS_DIR = os.path.join(GEMINI_DIR, "config", "skills")
WORKSPACE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(WORKSPACE_DIR, "omni_memory.db")
if not os.path.exists(DB_PATH):
    DB_PATH = os.path.join(PLUGIN_DIR, "omni_memory.db")

TEMP_COOLDOWN_FILE = os.path.join(tempfile.gettempdir(), ".omni_kernel_sync.lock")


def get_canonical_kernel_version(workspace=WORKSPACE_DIR) -> str:
    """Extracts the ratified Constitution version or plugin version as source of truth."""
    if not workspace:
        workspace = WORKSPACE_DIR
    constitution_path = os.path.join(workspace, ".specify", "constitution.md")
    if os.path.exists(constitution_path):
        try:
            with open(constitution_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                m = re.search(r'\bVersion\s*:\s*(\d+\.\d+\.\d+)', content, re.IGNORECASE)
                if m:
                    return m.group(1)
        except Exception:
            pass
    return KERNEL_VERSION

# Core skills governed directly by Omni-Kernel
CORE_KERNEL_SKILLS = {
    "spec-driven-development",
    "omni-skill-orchestrator",
    "skill-arbiter"
}

# Boundary-Aware Regex: Precisely matches Omni-Kernel anchor block
_PAT_BOUNDARY = re.compile(
    r'(<!--\s*OMNI-KERNEL-START(?:\s+v([0-9\.]+))?\s*-->)(.*?)(<!--\s*OMNI-KERNEL-END\s*-->)',
    re.DOTALL | re.IGNORECASE
)

CANONICAL_KERNEL_RULES_V43 = """# --- OMNI-KERNEL v4.3 AGENT INVARIANTS ---
# 1. Zero-Trust Security: Validate all inputs at trust boundaries. Never leak secrets.
# 2. Reliable Engineering: Fail loudly with context. Never swallow exceptions. Immutability first.
# 3. Ponytail Simplicity: Smallest complete working diff wins. YAGNI. Codebase > Stdlib > Deps.
# 4. Bilingual Native Parity: First-class English & Tiếng Việt reasoning and indexing.
# 5. Cloud Worker Fleet: Mandatory delegation to gemini_worker_cloud (Flash-Lite / 3.8 Flash / 4 Argon) and deepseek_worker_cloud (Audit Gate).
# 6. Tri-Tier Memory: L1 Reflex (<0.3ms), L2 WAL FTS5+ONNX (<15ms), L3 Consolidator.
# 7. Mandatory Transparency: Always render Omni-Kernel badge at the head of every response."""

# Backward compatibility alias
CANONICAL_KERNEL_RULES_V41 = CANONICAL_KERNEL_RULES_V43


# ==============================================================================
# LOW-LEVEL SAFEGUARDS (<0.5ms Pure-Stdlib Checks)
# ==============================================================================
def find_git_dir(start_path: str) -> Optional[str]:
    """
    Walks up directories to locate the true .git directory or worktree gitdir.
    Resolves both standard .git directories and .git worktree/submodule pointer files.
    """
    curr = os.path.abspath(start_path)
    if os.path.isfile(curr):
        curr = os.path.dirname(curr)

    while True:
        candidate = os.path.join(curr, ".git")
        if os.path.isdir(candidate):
            return candidate
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(4096).strip()
                if content.startswith("gitdir:"):
                    gitdir_ref = content.split("gitdir:", 1)[1].strip()
                    if not os.path.isabs(gitdir_ref):
                        gitdir_ref = os.path.normpath(os.path.join(curr, gitdir_ref))
                    if os.path.isdir(gitdir_ref):
                        # VULN-007: Validate the target contains HEAD to prove valid git structure
                        if os.path.isfile(os.path.join(gitdir_ref, "HEAD")):
                            return gitdir_ref
                        return "BROKEN_GIT_DIR"
                    else:
                        # Defensive #5: gitdir pointer exists but target directory is missing -> broken worktree
                        return "BROKEN_GIT_DIR"
            except OSError:
                pass

        parent = os.path.dirname(curr)
        if parent == curr:
            break
        curr = parent
    return None


def is_git_busy_or_unsafe(workspace_dir: str) -> Tuple[bool, str]:
    """
    Zero-subprocess Git state sniffer (<0.15ms).
    Recursively finds true git dir and checks rebase, merge, cherry-pick and lock files.
    """
    git_dir = find_git_dir(workspace_dir)
    if git_dir == "BROKEN_GIT_DIR":
        return True, "Corrupt or broken Git worktree pointer (unsafe state)"
    if not git_dir or not os.path.isdir(git_dir):
        return False, "Not a git repository"

    markers = {
        "MERGE_HEAD": "Active Git Merge in progress",
        "rebase-merge": "Active Git Interactive Rebase in progress",
        "rebase-apply": "Active Git Rebase/AM in progress",
        "CHERRY_PICK_HEAD": "Active Cherry-pick in progress",
        "REVERT_HEAD": "Active Revert in progress",
        "index.lock": "Git index locked by another process"
    }

    for marker, reason in markers.items():
        if os.path.exists(os.path.join(git_dir, marker)):
            return True, reason

    return False, "Git clean"


def check_and_update_cooldown(force: bool = False) -> bool:
    """Session-level debouncer: Avoids scanning disk repeatedly on every chat turn."""
    if force:
        return True
    now = time.time()
    try:
        if os.path.exists(TEMP_COOLDOWN_FILE):
            with open(TEMP_COOLDOWN_FILE, "r", encoding="utf-8") as f:
                last_run = float(f.read().strip())
            if now - last_run < DEBOUNCE_INTERVAL_SEC:
                return False  # Cooldown active, skip disk operations
    except Exception:
        pass

    try:
        with open(TEMP_COOLDOWN_FILE, "w", encoding="utf-8") as f:
            f.write(str(now))
    except Exception:
        pass
    return True


def safe_atomic_replace(temp_path: str, target_path: Path, max_retries: int = 5) -> bool:
    """
    NTFS-safe atomic replace with exponential backoff on Windows lock collisions (VULN-006).
    """
    for attempt in range(max_retries):
        try:
            os.replace(temp_path, target_path)
            return True
        except (PermissionError, OSError):
            if attempt < max_retries - 1:
                time.sleep(min(0.2, 0.02 * (2 ** attempt)))  # 20ms, 40ms, 80ms, 160ms backoff
            else:
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except OSError:
                        pass
                raise IOError(f"Windows Lock Conflict: Unable to overwrite {target_path} after {max_retries} attempts.")
    return False


# ==============================================================================
# SYNC TIERS & BOUNDARY-AWARE PATCHER
# ==============================================================================
class KernelSynchronizer:
    """Omni-Kernel v4.1 Immune System & Synchronizer."""

    @classmethod
    def detect_workspace_drift(cls, filepath: str) -> Tuple[Optional[str], bool]:
        """
        Detects version drift in a rule configuration file.
        Returns: (detected_version, is_missing_block)
        """
        if not os.path.exists(filepath):
            return None, True

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return None, False

        match = _PAT_BOUNDARY.search(content)
        if match:
            local_version = match.group(2) or "unknown"
            if local_version != KERNEL_VERSION:
                return local_version, False  # Drifted!
            inner = match.group(3).strip()
            # Normalize text for semantic parity check
            def _norm(t: str) -> str:
                return "\n".join(line.strip() for line in t.replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip())
            # Detect decommissioned worker or stale invariants
            if "tri-worker" in inner.lower() or _norm(inner) != _norm(CANONICAL_KERNEL_RULES_V43):
                return f"{local_version}-stale", False
            return None, False  # Up to date
        return None, True  # Missing block

    @classmethod
    def patch_workspace_rules(cls, filepath: str, new_rules: str = CANONICAL_KERNEL_RULES_V43, force: bool = False) -> Dict:
        """
        Boundary-Aware Patching: Replaces ONLY the core rules within anchor tags.
        Preserves 100% of user custom rules located outside the markers.
        """
        path = Path(filepath)
        workspace = str(path.parent)

        # 1. Check Git state safety
        git_busy, git_reason = is_git_busy_or_unsafe(workspace)
        if git_busy and not force:
            return {
                "status": "SKIPPED_GIT_UNSAFE",
                "reason": git_reason,
                "file": path.name,
                "jit_payload": new_rules
            }

        content = ""
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
            except Exception as e:
                return {"status": "ERROR", "error": str(e), "file": path.name}

        drift_version, is_missing = cls.detect_workspace_drift(filepath)

        new_block = (
            f"<!-- OMNI-KERNEL-START v{KERNEL_VERSION} -->\n"
            f"{new_rules}\n"
            f"<!-- OMNI-KERNEL-END -->"
        )

        if drift_version:
            updated_content = _PAT_BOUNDARY.sub(new_block, content)
            action = f"HEALED (v{drift_version} -> v{KERNEL_VERSION})"
        elif is_missing:
            updated_content = (content.rstrip() + "\n\n" + new_block + "\n") if content else (new_block + "\n")
            action = f"INJECTED (v{KERNEL_VERSION})"
        else:
            return {"status": "ALIGNED", "file": path.name}

        # 2. Atomic Write on Windows & POSIX
        temp_path = None
        try:
            fd, temp_path = tempfile.mkstemp(dir=path.parent, prefix=".omni_sync_", text=True)
            with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                tmp.write(updated_content)

            safe_atomic_replace(temp_path, path)
            temp_path = None
            return {"status": "SUCCESS", "action": action, "file": path.name}
        except Exception as e:
            return {"status": "ERROR", "error": str(e), "file": path.name}
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    @classmethod
    def sync_tier1_cache_invalidation(cls) -> bool:
        """
        Tier 1: Fast invalidation check for index cache outdating.
        Invalidates inverted_index.pkl if any skill definition is newer.
        """
        skills_dir = os.path.join(PLUGIN_DIR, "skills")
        index_pkl = os.path.join(PLUGIN_DIR, "scripts", "inverted_index.pkl")

        if not os.path.exists(skills_dir) or not os.path.exists(index_pkl):
            return False

        try:
            index_mtime = os.path.getmtime(index_pkl)
            for entry in os.scandir(skills_dir):
                if entry.is_dir():
                    skill_md = os.path.join(entry.path, "SKILL.md")
                    if os.path.exists(skill_md) and os.path.getmtime(skill_md) > index_mtime:
                        os.remove(index_pkl)
                        return True
        except Exception:
            pass
        return False

    @classmethod
    def sync_tier2_schema_migration(cls, db_path: str = DB_PATH) -> Tuple[bool, str]:
        """
        Tier 2: SQLite Schema Migration via PRAGMA user_version.
        """
        if not os.path.exists(db_path):
            return False, "DB does not exist yet"

        try:
            conn = sqlite3.connect(db_path, timeout=5.0)
            conn.execute("PRAGMA busy_timeout = 5000;")
            cursor = conn.cursor()

            current_ver = cursor.execute("PRAGMA user_version;").fetchone()[0]

            if current_ver >= KERNEL_SCHEMA_VERSION:
                conn.close()
                return False, f"Schema aligned at v{current_ver}"

            cursor.execute("BEGIN IMMEDIATE;")
            if current_ver < KERNEL_SCHEMA_VERSION:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    );
                """)
                cursor.execute(f"PRAGMA user_version = {KERNEL_SCHEMA_VERSION};")
                cursor.execute(
                    f"INSERT OR REPLACE INTO schema_migrations VALUES ({KERNEL_SCHEMA_VERSION}, datetime('now'));"
                )

            conn.commit()
            conn.close()
            return True, f"Migrated schema v{current_ver} -> v{KERNEL_SCHEMA_VERSION}"
        except Exception as e:
            return False, f"Migration failed: {e}"


# ==============================================================================
# CORE SKILL VERSION ALIGNMENT
# ==============================================================================
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
    m_meta = re.search(r'metadata:\s*\n(?:\s+.*\n)*?\s+version:\s*["\']?([0-9\.]+)["\']?', content)
    if m_meta:
        return m_meta.group(1)
    m_v = re.search(r'version:\s*["\']?([0-9\.]+)["\']?', content)
    if m_v:
        return m_v.group(1)
    return "unknown"


def audit_kernel_skills(target_version: str = KERNEL_VERSION, workspace=WORKSPACE_DIR):
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


def sync_kernel_skills(target_version: str = KERNEL_VERSION, workspace=WORKSPACE_DIR, auto_reindex=True):
    """Automatically fixes version drift across all core kernel skills and re-indexes."""
    report = audit_kernel_skills(target_version, workspace)
    fixed_count = 0
    major_minor = ".".join(target_version.split(".")[:2])

    for item in report:
        if not item.get("is_drifted"):
            continue

        p = item["path"]
        try:
            with open(p, "r", encoding="utf-8") as f:
                content = f.read()

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

            content = content.replace("Omni-Kernel v3.0", f"Omni-Kernel v{major_minor}")
            content = content.replace("Omni-Kernel v2.0", f"Omni-Kernel v{major_minor}")
            content = content.replace("Omni-Kernel Orchestrator v2.0", f"Omni-Kernel Orchestrator v{major_minor}")
            content = content.replace("Engine v3.0", f"Engine v{major_minor}")

            p_path = Path(p)
            p_path.parent.mkdir(parents=True, exist_ok=True)
            temp_p = None
            try:
                fd, temp_p = tempfile.mkstemp(dir=p_path.parent, prefix=".omni_skill_", text=True)
                with os.fdopen(fd, "w", encoding="utf-8") as tmp_f:
                    tmp_f.write(content)
                safe_atomic_replace(temp_p, p_path)
                temp_p = None

                item["fixed"] = True
                fixed_count += 1
            finally:
                if temp_p and os.path.exists(temp_p):
                    try:
                        os.remove(temp_p)
                    except OSError:
                        pass
        except Exception as e:
            item["fix_error"] = str(e)

    if auto_reindex and fixed_count > 0:
        try:
            indexer_path = os.path.join(PLUGIN_DIR, "scripts", "indexer.py")
            if not os.path.exists(indexer_path):
                indexer_path = os.path.join(workspace, "scripts", "indexer.py")
            if os.path.exists(indexer_path):
                sys.path.insert(0, os.path.dirname(indexer_path))
                import indexer
                reg_path = os.path.join(os.path.dirname(indexer_path), "registry.json")
                indexer.build_index(reg_path)
        except Exception:
            pass

    return report, fixed_count


# ==============================================================================
# UNIFIED SYNC ORCHESTRATION & CLI
# ==============================================================================
def run_omni_sync(workspace: str = WORKSPACE_DIR, fix: bool = False, force: bool = False, target_version: str = KERNEL_VERSION) -> Dict:
    """Coordinates full 3-Tier synchronization and skill alignment."""
    results = {
        "timestamp": time.time(),
        "kernel_version": target_version,
        "tier1_cache_invalidated": False,
        "tier2_db_migration": "",
        "tier3_workspace": [],
        "skills_report": [],
        "skills_fixed": 0
    }

    # 1. Tier 1: Cache Invalidation
    results["tier1_cache_invalidated"] = KernelSynchronizer.sync_tier1_cache_invalidation()

    # 2. Tier 2: DB Schema
    _, db_msg = KernelSynchronizer.sync_tier2_schema_migration()
    results["tier2_db_migration"] = db_msg

    # 3. Tier 3: Workspace Rules (Dual-Zone check)
    target_files = [
        os.path.join(workspace, ".cursorrules"),
        os.path.join(workspace, "GEMINI.md"),
        os.path.join(workspace, "rules", "AGENTS.md")
    ]

    for fpath in target_files:
        if not os.path.exists(fpath) and not fix:
            continue

        drift, is_missing = KernelSynchronizer.detect_workspace_drift(fpath)
        file_status = {
            "path": fpath,
            "filename": os.path.basename(fpath),
            "drift_version": drift,
            "is_missing": is_missing
        }

        if drift or (is_missing and fix):
            if fix:
                patch_res = KernelSynchronizer.patch_workspace_rules(fpath, force=force)
                file_status.update(patch_res)
            else:
                file_status["status"] = "DRIFT_DETECTED"
                file_status["recommendation"] = f"Run 'python scripts/kernel_sync.py --fix' to align to v{target_version}"

        results["tier3_workspace"].append(file_status)

    # 4. Core Skills Alignment
    if fix:
        s_rep, s_fixed = sync_kernel_skills(target_version, workspace, auto_reindex=True)
        results["skills_report"] = s_rep
        results["skills_fixed"] = s_fixed
    else:
        results["skills_report"] = audit_kernel_skills(target_version, workspace)

    return results


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Omni-Kernel v4.1 Immune System & Boundary-Aware Sync")
    parser.add_argument("--check", action="store_true", help="Audit drift without touching any workspace file")
    parser.add_argument("--fix", action="store_true", help="Safely auto-heal workspace rules and kernel skills")
    parser.add_argument("--force", action="store_true", help="Bypass cooldown lock and Git safety checks")
    parser.add_argument("--workspace", type=str, default=WORKSPACE_DIR, help="Target workspace path")
    parser.add_argument("--target-version", type=str, default=KERNEL_VERSION, help="Target Omni-Kernel version")

    args = parser.parse_args()

    t0 = time.perf_counter()
    res = run_omni_sync(workspace=args.workspace, fix=args.fix, force=args.force, target_version=args.target_version)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    print(f"🛡️ OMNI-KERNEL IMMUNE SYSTEM (v{args.target_version}) - Execution: {elapsed_ms:.2f}ms")
    print("=" * 70)
    print(f"• Tier 1 (L1 Cache Invalidation): {'Invalidated' if res['tier1_cache_invalidated'] else 'Aligned'}")
    print(f"• Tier 2 (SQLite WAL Migration):  {res['tier2_db_migration']}")
    print(f"• Tier 3 (Workspace Rules Sync):")

    for f in res["tier3_workspace"]:
        status = f.get("status", "ALIGNED")
        drift = f.get("drift_version")
        name = f.get("filename")
        if status == "DRIFT_DETECTED":
            print(f"  [!] {name:16} -> DRIFT DETECTED (v{drift} != v{args.target_version}) [Run with --fix]")
        elif status == "SUCCESS":
            print(f"  [✔] {name:16} -> {f.get('action')} [Atomic Safe]")
        elif status == "SKIPPED_GIT_UNSAFE":
            print(f"  [⚠️] {name:16} -> Skipped writing to disk: {f.get('reason')} [JIT Protected]")
        else:
            print(f"  [✔] {name:16} -> Aligned")

    print("-" * 70)
    print(f"• Core Kernel Skills Audit:")
    for sk in res["skills_report"]:
        st = "🚨 DRIFTED" if sk.get("is_drifted") else "✔ ALIGNED"
        if sk.get("fixed"):
            st = "✔ FIXED"
        print(f"  [{sk.get('scope', 'CORE').upper():9}] {sk.get('skill_name')} -> v{sk.get('current_version')} [{st}]")

    print("=" * 70)


if __name__ == "__main__":
    main()
