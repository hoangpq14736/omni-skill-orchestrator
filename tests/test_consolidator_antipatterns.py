import os
import sys
import tempfile
import unittest
import sqlite3

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from memory_schema import init_database
from memory_engine import record_antipattern
from consolidator import ConsolidatorEngine


class TestConsolidatorAntipatternSweep(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_sweep.db")
        self.conn = init_database(self.db_path)
        self.ws_dir = os.path.join(self.tmp_dir.name, "sweep_ws")
        os.makedirs(self.ws_dir, exist_ok=True)
        self.engine = ConsolidatorEngine(self.conn, workspace_root=self.ws_dir, allow_unscoped=True)

    def tearDown(self):
        self.conn.close()
        self.tmp_dir.cleanup()

    def test_01_proactive_ttl_sweep_in_batch_consolidation(self):
        """Verify that consolidator proactively soft-archives expired antipatterns."""
        # 1. Insert an active antipattern with ttl_days=14.0 (created right now)
        active_id = record_antipattern(
            conn_or_db=self.conn,
            workspace_dir=self.ws_dir,
            tool_name="run_command",
            command_pattern="active command",
            error_signature="ActiveError",
            root_cause="Active failure",
            mitigation_guidance="Do something",
            ttl_days=14.0
        )

        # 2. Insert an expired antipattern (created 15 days ago)
        expired_id = record_antipattern(
            conn_or_db=self.conn,
            workspace_dir=self.ws_dir,
            tool_name="run_command",
            command_pattern="expired command",
            error_signature="ExpiredError",
            root_cause="Old failure",
            mitigation_guidance="Do old thing",
            ttl_days=14.0
        )
        # Backdate created_at to 15 days ago
        with self.conn:
            self.conn.execute(
                "UPDATE episodic_antipatterns SET created_at = datetime('now', '-15 days') WHERE antipattern_id = ?",
                (expired_id,)
            )

        # Run consolidate_batch
        res = self.engine.consolidate_batch()
        self.assertIn("antipatterns_archived", res)
        self.assertGreaterEqual(res["antipatterns_archived"], 1)

        # Verify database statuses
        cur = self.conn.cursor()
        cur.execute("SELECT status FROM episodic_antipatterns WHERE antipattern_id = ?", (active_id,))
        self.assertEqual(cur.fetchone()[0], "Active", "Fresh antipattern must stay Active")

        cur.execute("SELECT status FROM episodic_antipatterns WHERE antipattern_id = ?", (expired_id,))
        self.assertEqual(cur.fetchone()[0], "Archived", "Expired antipattern must be proactively Archived")


if __name__ == "__main__":
    unittest.main()
