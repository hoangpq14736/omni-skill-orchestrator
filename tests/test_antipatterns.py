import os
import sys
import time
import tempfile
import unittest
import sqlite3
import datetime

# Ensure scripts directory is on path
_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from memory_schema import init_database
from memory_engine import record_antipattern, recall_antipatterns
from experiential_memory import seed_canonical_traces, recall_traces


class TestEpisodicAntipatterns(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_antipatterns.db")
        self.conn = init_database(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmp_dir.cleanup()

    def test_01_record_and_recall_antipattern(self):
        """Verify recording and recalling antipatterns from SQLite WAL."""
        ws_dir = os.path.join(self.tmp_dir.name, "workspace_a")
        os.makedirs(ws_dir, exist_ok=True)

        ap_id = record_antipattern(
            conn_or_db=self.conn,
            workspace_dir=ws_dir,
            tool_name="run_command",
            command_pattern="python -c .*?",
            error_signature="CommandNotFoundException",
            root_cause="PowerShell parses .*? as a cmdlet when double quotes are unescaped",
            mitigation_guidance="Use single quotes or write script to scratch directory first",
            ttl_days=14.0
        )
        self.assertIsNotNone(ap_id)

        # Recall with matching tool and command pattern
        matches = recall_antipatterns(
            conn_or_db=self.conn,
            workspace_dir=ws_dir,
            tool_name="run_command",
            command_text='python -c "import re; re.findall(r\'.*?\', text)"'
        )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["antipattern_id"], ap_id)
        self.assertEqual(matches[0]["trigger_count"], 1)
        self.assertIn("PowerShell parses", matches[0]["root_cause"])
        self.assertIsNotNone(matches[0]["last_triggered_at"])

    def test_02_ttl_soft_archiving(self):
        """Verify expired antipatterns are soft-archived rather than hard-deleted."""
        ws_dir = os.path.join(self.tmp_dir.name, "workspace_b")
        os.makedirs(ws_dir, exist_ok=True)

        ap_id = record_antipattern(
            conn_or_db=self.conn,
            workspace_dir=ws_dir,
            tool_name="git",
            command_pattern="git checkout -b",
            error_signature="fatal: a branch named already exists",
            root_cause="Branch exists",
            mitigation_guidance="Use git switch or git checkout existing",
            ttl_days=0.0  # Immediately expired
        )

        matches = recall_antipatterns(
            conn_or_db=self.conn,
            workspace_dir=ws_dir,
            tool_name="git"
        )
        self.assertEqual(len(matches), 0, "Expired antipattern should not be returned")

        # Verify soft-archive in database
        cur = self.conn.cursor()
        cur.execute("SELECT status FROM episodic_antipatterns WHERE antipattern_id = ?", (ap_id,))
        status = cur.fetchone()[0]
        self.assertEqual(status, "Archived", "Expired record must have status='Archived'")

    def test_03_dynamic_adaptive_threshold_short_vs_long_queries(self):
        """Verify dynamic adaptive threshold protects short queries while blocking noise in long queries."""
        traces_path = os.path.join(self.tmp_dir.name, "test_traces.json")
        seed_canonical_traces(traces_path)

        # Short query (<= 3 tokens) -> adaptive threshold 0.28 kicks in
        short_res = recall_traces(
            "lỗi docker port",
            traces_path=traces_path,
            allow_unscoped=True
        )
        self.assertGreater(len(short_res), 0, "Short query should recall matching trace via 0.28 threshold")

        # Long noisy query (> 3 tokens) -> strict 0.335 threshold prevents false positive
        long_noisy_res = recall_traces(
            "kết hợp cùng các worker triển khai từng bước một nâng cấp đi",
            traces_path=traces_path,
            allow_unscoped=True
        )
        self.assertEqual(len(long_noisy_res), 0, "Long query with accidental partial match should be rejected")


if __name__ == "__main__":
    unittest.main()
