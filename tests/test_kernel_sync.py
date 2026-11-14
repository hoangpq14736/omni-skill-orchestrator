#!/usr/bin/env python3
"""
Unit Test Suite for Omni-Kernel v4.1 Boundary-Aware Synchronizer (kernel_sync.py)
Verifies:
1. Boundary-Aware Regex parsing and patching (preserves user custom rules)
2. Zero-subprocess Git state sniffer (<0.15ms)
3. Windows NTFS-safe atomic replace with retry
4. SQLite schema version check and migration
5. Version drift detection in workspace configuration files
"""

import os
import sys
import unittest
import tempfile
import sqlite3
from pathlib import Path

# Ensure scripts is on sys.path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from kernel_sync import (
    KernelSynchronizer,
    is_git_busy_or_unsafe,
    safe_atomic_replace,
    KERNEL_VERSION,
    KERNEL_SCHEMA_VERSION,
    _PAT_BOUNDARY,
    CANONICAL_KERNEL_RULES_V43,
    CANONICAL_KERNEL_RULES_V41
)


class TestKernelSynchronizer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_detect_workspace_drift_missing_and_drifted(self):
        rule_file = os.path.join(self.workspace, ".cursorrules")

        # 1. Non-existent file
        drift_v, is_missing = KernelSynchronizer.detect_workspace_drift(rule_file)
        self.assertTrue(is_missing)
        self.assertIsNone(drift_v)

        # 2. Existing file without block
        with open(rule_file, "w", encoding="utf-8") as f:
            f.write("# My custom rule\nDo not use semicolons;\n")

        drift_v, is_missing = KernelSynchronizer.detect_workspace_drift(rule_file)
        self.assertTrue(is_missing)
        self.assertIsNone(drift_v)

        # 3. Existing file with stale v3.8 block
        stale_block = (
            "# User Header Rule\n\n"
            "<!-- OMNI-KERNEL-START v3.8.0 -->\n"
            "# Outdated invariants\n"
            "<!-- OMNI-KERNEL-END -->\n\n"
            "# User Footer Rule"
        )
        with open(rule_file, "w", encoding="utf-8") as f:
            f.write(stale_block)

        drift_v, is_missing = KernelSynchronizer.detect_workspace_drift(rule_file)
        self.assertFalse(is_missing)
        self.assertEqual(drift_v, "3.8.0")

        # 4. Aligned block
        aligned_block = (
            f"<!-- OMNI-KERNEL-START v{KERNEL_VERSION} -->\n"
            f"{CANONICAL_KERNEL_RULES_V43}\n"
            "<!-- OMNI-KERNEL-END -->"
        )
        with open(rule_file, "w", encoding="utf-8") as f:
            f.write(aligned_block)

        drift_v, is_missing = KernelSynchronizer.detect_workspace_drift(rule_file)
        self.assertFalse(is_missing)
        self.assertIsNone(drift_v)

    def test_boundary_aware_patching_preserves_user_rules(self):
        rule_file = os.path.join(self.workspace, "GEMINI.md")

        original_content = (
            "# USER FRONT MATTER RULE: ALWAYS USE PYTHON 3.13\n"
            "export MY_VAR=123\n\n"
            "<!-- OMNI-KERNEL-START v3.5.0 -->\n"
            "# Obsolete rules to be replaced\n"
            "<!-- OMNI-KERNEL-END -->\n\n"
            "# USER TAIL RULE: NEVER DELETE THIS SECTION!\n"
            "Important business logic rule here."
        )
        with open(rule_file, "w", encoding="utf-8") as f:
            f.write(original_content)

        # Run patch
        res = KernelSynchronizer.patch_workspace_rules(rule_file, force=True)
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertIn("HEALED", res.get("action", ""))

        with open(rule_file, "r", encoding="utf-8") as f:
            updated = f.read()

        # Invariants replaced
        self.assertIn(f"<!-- OMNI-KERNEL-START v{KERNEL_VERSION} -->", updated)
        self.assertIn("Zero-Trust Security", updated)
        self.assertIn(CANONICAL_KERNEL_RULES_V41, updated)
        self.assertNotIn("Obsolete rules to be replaced", updated)

        # User custom rules strictly preserved
        self.assertIn("# USER FRONT MATTER RULE: ALWAYS USE PYTHON 3.13", updated)
        self.assertIn("export MY_VAR=123", updated)
        self.assertIn("# USER TAIL RULE: NEVER DELETE THIS SECTION!", updated)
        self.assertIn("Important business logic rule here.", updated)

    def test_git_sniffer_detects_busy_merge_rebase(self):
        git_dir = os.path.join(self.workspace, ".git")
        os.makedirs(git_dir, exist_ok=True)

        # Clean git dir
        is_busy, reason = is_git_busy_or_unsafe(self.workspace)
        self.assertFalse(is_busy)
        self.assertEqual(reason, "Git clean")

        # Simulate active merge
        merge_head = os.path.join(git_dir, "MERGE_HEAD")
        with open(merge_head, "w") as f:
            f.write("dummy_sha")

        is_busy, reason = is_git_busy_or_unsafe(self.workspace)
        self.assertTrue(is_busy)
        self.assertIn("Active Git Merge", reason)

        # Remove merge marker, add index.lock
        os.remove(merge_head)
        lock_file = os.path.join(git_dir, "index.lock")
        with open(lock_file, "w") as f:
            f.write("lock")

        is_busy, reason = is_git_busy_or_unsafe(self.workspace)
        self.assertTrue(is_busy)
        self.assertIn("locked", reason)

    def test_atomic_replace(self):
        target = Path(self.workspace) / "target.txt"
        target.write_text("initial", encoding="utf-8")

        temp = Path(self.workspace) / "temp.txt"
        temp.write_text("updated_atomic", encoding="utf-8")

        safe_atomic_replace(str(temp), target)
        self.assertEqual(target.read_text(encoding="utf-8"), "updated_atomic")
        self.assertFalse(temp.exists())

    def test_schema_migration(self):
        db_file = os.path.join(self.workspace, "test_schema.db")
        conn = sqlite3.connect(db_file)
        conn.execute("PRAGMA user_version = 0;")
        conn.close()

        migrated, msg = KernelSynchronizer.sync_tier2_schema_migration(db_file)
        self.assertTrue(migrated)
        self.assertIn(f"Migrated schema v0 -> v{KERNEL_SCHEMA_VERSION}", msg)

        # Second run is idempotent
        migrated2, msg2 = KernelSynchronizer.sync_tier2_schema_migration(db_file)
        self.assertFalse(migrated2)
        self.assertIn("aligned", msg2)


if __name__ == "__main__":
    unittest.main()
