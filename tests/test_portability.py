#!/usr/bin/env python3
"""
Unit tests for Omni-Kernel v4.1 Universal Portability Layer.
Tests Git-Root Identity, dual-hash resolution, hybrid DB paths, and PII freedom.
"""

import os
import sys
import unittest
from pathlib import Path

# Add scripts directory to path
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from memory_utils import (
    resolve_git_remote_url,
    git_workspace_hash,
    get_workspace_hashes,
    canonical_workspace_hash,
    get_omni_memory_db_path,
    is_valid_hex_hash,
)
from backend_client import poll_socket_alive, is_local_worker_available


class TestUniversalPortability(unittest.TestCase):

    def setUp(self):
        self.workspace_root = Path(__file__).resolve().parent.parent

    def test_resolve_git_remote_url(self):
        """Verify git remote origin URL is cleanly resolved from current workspace."""
        if not (self.workspace_root / ".git").exists():
            self.skipTest("Not a git repository (standalone plugin environment)")
        url = resolve_git_remote_url(str(self.workspace_root))
        self.assertIsNotNone(url)
        self.assertIn("github.com", url)
        self.assertIn("omni-skill-orchestrator", url)
        self.assertFalse(url.endswith(".git"), "Normalized url must strip .git suffix")

    def test_git_workspace_hash(self):
        """Verify git_workspace_hash produces valid 64-character SHA-256."""
        if not (self.workspace_root / ".git").exists():
            self.skipTest("Not a git repository (standalone plugin environment)")
        gh = git_workspace_hash(str(self.workspace_root))
        self.assertIsNotNone(gh)
        self.assertTrue(is_valid_hex_hash(gh, length=64))

    def test_get_workspace_hashes_dual_lookup(self):
        """Verify get_workspace_hashes returns both canonical path hash and git hash."""
        hashes = get_workspace_hashes(str(self.workspace_root))
        self.assertIsInstance(hashes, list)
        if (self.workspace_root / ".git").exists():
            self.assertGreaterEqual(len(hashes), 2)
            git_h = git_workspace_hash(str(self.workspace_root))
            self.assertIn(git_h, hashes)
        else:
            self.assertGreaterEqual(len(hashes), 1)
        # All returned hashes must be valid 64-hex
        for h in hashes:
            self.assertTrue(is_valid_hex_hash(h, length=64))
        # Canonical path hash must be included
        path_h = canonical_workspace_hash(str(self.workspace_root))
        self.assertIn(path_h, hashes)

    def test_get_omni_memory_db_path_hybrid(self):
        """Verify hybrid DB resolution respects local dev lab vs global user path."""
        # 1. Local workspace lab contains omni_memory.db -> should return local
        local_db = get_omni_memory_db_path(str(self.workspace_root))
        self.assertTrue(os.path.isabs(local_db))
        self.assertTrue(local_db.endswith("omni_memory.db"))

        # 2. Non-existent workspace without local db -> should default to global ~/.gemini/
        dummy_ws = self.workspace_root / "specs" / "001-omni-memory-v4"
        global_fallback = get_omni_memory_db_path(str(dummy_ws))
        self.assertIn(".gemini", global_fallback)

    def test_no_hardcoded_pii_in_agents_rules(self):
        """Verify rules/AGENTS.md does not leak credentials or external PII."""
        agents_rule = self.workspace_root / "rules" / "AGENTS.md"
        if agents_rule.is_file():
            content = agents_rule.read_text(encoding="utf-8")
            self.assertNotIn("ghp_", content)
            self.assertNotIn("sk-proj-", content)
            self.assertNotIn("sk-ant-", content)

    def test_local_worker_probe(self):
        """Verify local worker probe executes cleanly without hanging."""
        res = is_local_worker_available(timeout_sec=0.2)
        self.assertIsInstance(res, bool)

    def test_resolve_git_remote_url_worktree_pointer(self):
        """Verify resolve_git_remote_url resolves .git worktree pointer files via commondir."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            main_git = root / "repo" / ".git"
            wt_gitdir = main_git / "worktrees" / "wt1"
            wt_root = root / "wt1"
            wt_gitdir.mkdir(parents=True)
            wt_root.mkdir(parents=True)
            (main_git / "config").write_text(
                '[remote "origin"]\n\turl = https://github.com/example/Omni-Repo.git\n',
                encoding="utf-8",
            )
            (wt_gitdir / "commondir").write_text("../..\n", encoding="utf-8")
            (wt_root / ".git").write_text(f"gitdir: {wt_gitdir}\n", encoding="utf-8")

            self.assertEqual(
                resolve_git_remote_url(str(wt_root)),
                "https://github.com/example/omni-repo",
            )


if __name__ == "__main__":
    unittest.main()
