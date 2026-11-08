import os
import sys
import tempfile
import unittest

_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from memory_schema import init_database
from antipattern_guard import classify_cli_error, handle_post_execution
from memory_engine import recall_antipatterns


class TestAntipatternGuard(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp_dir.name, "test_guard.db")
        self.conn = init_database(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmp_dir.cleanup()

    def test_01_filter_out_transient_typos(self):
        """Verify that file typos and transient locks are completely filtered out (NOT recorded)."""
        # Typo: File not found
        res1 = classify_cli_error(
            tool_name="run_command",
            command="python non_existent_script.py",
            exit_code=1,
            output_text="python: can't open file 'non_existent_script.py': [Errno 2] No such file or directory"
        )
        self.assertIsNone(res1, "File not found / typo errors must be filtered out")

        # Transient lock
        res2 = classify_cli_error(
            tool_name="run_command",
            command="python scripts/consolidator.py",
            exit_code=1,
            output_text="sqlite3.OperationalError: database is locked"
        )
        self.assertIsNone(res2, "Transient lock errors must be filtered out")

        # User interrupt
        res3 = classify_cli_error(
            tool_name="run_command",
            command="npm run dev",
            exit_code=130,
            output_text="KeyboardInterrupt"
        )
        self.assertIsNone(res3, "User interrupts must be filtered out")

    def test_02_classify_structural_failures(self):
        """Verify that genuine syntax, quote, and schema mismatch failures are correctly captured."""
        # PowerShell escaping failure
        res_ps = classify_cli_error(
            tool_name="run_command",
            command='python -c "import re; re.findall(r\'.*?\', text)"',
            exit_code=1,
            output_text=".*? : The term '.*?' is not recognized as the name of a cmdlet, function, script file"
        )
        self.assertIsNotNone(res_ps)
        self.assertIn("PowerShell regex quoting failure", res_ps["root_cause"])
        self.assertIn("single quotes", res_ps["mitigation_guidance"])

        # SQLite schema mismatch
        res_sql = classify_cli_error(
            tool_name="run_command",
            command="python -c \"SELECT * FROM files\"",
            exit_code=1,
            output_text="sqlite3.OperationalError: no such table: files"
        )
        self.assertIsNotNone(res_sql)
        self.assertIn("SQLite schema mismatch", res_sql["root_cause"])

    def test_03_handle_post_execution_deduplication(self):
        """Verify autonomous post-execution logging and deduplication in SQLite WAL."""
        ws_dir = os.path.join(self.tmp_dir.name, "test_ws")
        os.makedirs(ws_dir, exist_ok=True)

        # 1. Ignored error does not touch database
        ignored = handle_post_execution(
            workspace_dir=ws_dir,
            tool_name="run_command",
            command_line="python typo.py",
            exit_code=1,
            output_text="FileNotFoundError: [Errno 2] No such file or directory: 'typo.py'",
            conn_or_db=self.conn
        )
        self.assertIsNone(ignored)

        all_stored = recall_antipatterns(self.conn, workspace_dir=ws_dir)
        self.assertEqual(len(all_stored), 0, "No antipattern should be stored for typo")

        # 2. Structural error is recorded
        cmd = 'python -c "import re; re.findall(r\'.*?\', t)"'
        err_out = ".*? : The term '.*?' is not recognized as the name of a cmdlet"

        first_rec = handle_post_execution(
            workspace_dir=ws_dir,
            tool_name="run_command",
            command_line=cmd,
            exit_code=1,
            output_text=err_out,
            conn_or_db=self.conn
        )
        self.assertIsNotNone(first_rec)
        ap_id = first_rec.get("antipattern_id")
        self.assertIsNotNone(ap_id)

        stored = recall_antipatterns(self.conn, workspace_dir=ws_dir)
        self.assertEqual(len(stored), 1, "Exactly one antipattern record should exist")

        # 3. Repeated error reinforces existing antipattern (no bloat)
        second_rec = handle_post_execution(
            workspace_dir=ws_dir,
            tool_name="run_command",
            command_line=cmd,
            exit_code=1,
            output_text=err_out,
            conn_or_db=self.conn
        )
        self.assertIsNotNone(second_rec)
        self.assertEqual(second_rec["antipattern_id"], ap_id)

        stored_after = recall_antipatterns(self.conn, workspace_dir=ws_dir)
        self.assertEqual(len(stored_after), 1, "Table count must NOT increase on duplicate failure")
        self.assertGreaterEqual(stored_after[0]["trigger_count"], 1)


if __name__ == "__main__":
    unittest.main()
