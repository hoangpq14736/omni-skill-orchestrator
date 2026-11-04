#!/usr/bin/env python3
"""
Unit Test Suite for Omni-Kernel v4.1 Pure SQLite Algebraic Ebbinghaus Decay (Session 2 Upgrade)
Verifies:
1. Padé [0/1] algebraic decay computed directly in SQLite
2. Time-partitioned decay execution (< 1 day protection)
3. 7-day grace period for newly created memories
4. Invariant permanence (memory_type == 'invariant' NEVER decays or archives)
5. Two-phase soft-archiving (<0.20 threshold) and hard-purging (>30 days)
"""

import os
import sys
import unittest
import tempfile
import sqlite3
from datetime import datetime, timezone, timedelta

# Ensure scripts is on sys.path
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from consolidator import ConsolidatorEngine
from memory_schema import init_database


class TestEbbinghausAlgebraicDecay(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_decay.db")
        self.conn = init_database(self.db_path)
        self.engine = ConsolidatorEngine(self.conn, allow_unscoped=True)

    def tearDown(self):
        self.conn.close()
        self.temp_dir.cleanup()

    def test_algebraic_decay_and_grace_period(self):
        cur = self.conn.cursor()
        now = datetime.now(timezone.utc)

        # 1. Hot memory (3 hours ago) -> Protected from decay (< 1 day old)
        hot_time = (now - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, solution_payload, content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES ('mem-hot', 'h1', '/ws', 'proven_trace', 'Hot', 'Sol', 'hot', 'Active', 1, 1.0, 0.08, ?, ?)
            """,
            (hot_time, hot_time)
        )

        # 2. Invariant memory (100 days old) -> NEVER decays or archives
        inv_time = (now - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, solution_payload, content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES ('mem-inv', 'h1', '/ws', 'invariant', 'Inv', 'Sol', 'inv', 'Active', 5, 1.0, 0.0, ?, ?)
            """,
            (inv_time, inv_time)
        )

        # 3. Decayed memory past 7 days (25 days old, activation_count=1, decay=0.30)
        # Padé score = 1.5 / (1.5 + 0.30 * 25) = 1.5 / 9.0 ~ 0.166 < 0.20
        # Should be soft-archived (not hard-purged since < 30 days old)!
        decayed_time = (now - timedelta(days=25)).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, solution_payload, content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES ('mem-stale', 'h1', '/ws', 'proven_trace', 'Stale', 'Sol', 'stale', 'Active', 1, 1.0, 0.30, ?, ?)
            """,
            (decayed_time, decayed_time)
        )

        # 4. Archived memory older than 35 days -> Should be hard-purged!
        archived_old_time = (now - timedelta(days=35)).strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """
            INSERT INTO workspace_episodic_memory (
                memory_id, workspace_hash, workspace_path, memory_type,
                title, solution_payload, content_folded, status, activation_count, confidence_score,
                decay_rate, last_accessed_at, created_at
            ) VALUES ('mem-purge', 'h1', '/ws', 'proven_trace', 'Purge', 'Sol', 'purge', 'Archived', 1, 0.05, 0.20, ?, ?)
            """,
            (archived_old_time, archived_old_time)
        )

        self.conn.commit()

        # Run consolidation batch
        res = self.engine.consolidate_batch(batch_size=50, dry_run=False)

        # Verify mem-hot retained confidence 1.0
        cur.execute("SELECT confidence_score, status FROM workspace_episodic_memory WHERE memory_id = 'mem-hot'")
        r_hot = cur.fetchone()
        self.assertEqual(r_hot[0], 1.0)
        self.assertEqual(r_hot[1], 'Active')

        # Verify mem-inv retained confidence 1.0 and status Active
        cur.execute("SELECT confidence_score, status FROM workspace_episodic_memory WHERE memory_id = 'mem-inv'")
        r_inv = cur.fetchone()
        self.assertEqual(r_inv[0], 1.0)
        self.assertEqual(r_inv[1], 'Active')

        # Verify mem-stale was soft-archived because Padé score < 0.20
        cur.execute("SELECT confidence_score, status FROM workspace_episodic_memory WHERE memory_id = 'mem-stale'")
        r_stale = cur.fetchone()
        self.assertLess(r_stale[0], 0.20)
        self.assertEqual(r_stale[1], 'Archived')

        # Verify mem-purge was hard-purged from the database
        cur.execute("SELECT count(*) FROM workspace_episodic_memory WHERE memory_id = 'mem-purge'")
        self.assertEqual(cur.fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
