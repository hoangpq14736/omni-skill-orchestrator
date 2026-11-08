"""Live Integration Test for Omni-Graph Engine."""

import unittest
import os
import sys
import tempfile
import sqlite3
from pathlib import Path

# Add scripts directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from omni_graph.storage import (
    get_connection,
    init_db,
    clean_orphan_edges,
    delete_file_records,
)
from omni_graph.git_hygiene import ensure_git_hygiene
from omni_graph.fingerprint import detect_dirty_files, scan_workspace_files
from omni_graph.visitor import parse_python_file
from omni_graph.validator import (
    HardenedSignatureContractValidator,
    validate_call_site,
)
from omni_graph.lifecycle import LifecycleRegistrationGuard
from omni_graph.traversal import compute_blast_radius, query_callers, query_callees
from omni_graph.visualizer import generate_graph_html
from omni_graph.self_healing import micro_index_file

class TestOmniGraphLive(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_git_hygiene(self):
        res1 = ensure_git_hygiene(self.workspace)
        self.assertTrue(res1)
        gitignore = self.workspace / ".gitignore"
        self.assertTrue(gitignore.exists())
        self.assertIn(".omni/", gitignore.read_text(encoding="utf-8"))

        # Second run should return False (already present)
        res2 = ensure_git_hygiene(self.workspace)
        self.assertFalse(res2)

    def test_storage_and_ast_parsing(self):
        conn = get_connection(self.workspace)
        init_db(conn)
        try:
            # Create a sample python file
            test_py = self.workspace / "service.py"
            test_py.write_text(
                """
class UserService:
    def create_user(self, username: str, email: str, role: str = 'user') -> dict:
        \"\"\"Create a new user.\"\"\"
        return {'username': username, 'role': role}

def helper():
    svc = UserService()
    return svc.create_user(username='alice', email='a@example.com')
""",
                encoding="utf-8",
            )

            nodes, sigs, edges, hooks, status, err = parse_python_file("service.py", "service.py", str(test_py))
            self.assertEqual(status, "SUCCESS")
            self.assertTrue(len(nodes) >= 3)
            self.assertTrue(len(sigs) >= 2)
            self.assertTrue(len(edges) >= 1)

            # Micro-index file
            heal_res = micro_index_file(self.workspace, "service.py")
            self.assertEqual(heal_res["status"], "SUCCESS")

            # Test signature validator on create_user
            res_ok = validate_call_site(conn, "create_user", 0, ["username", "email"])
            self.assertTrue(res_ok.is_valid)

            # Test unexpected keyword arg
            res_bad = validate_call_site(conn, "create_user", 0, ["username", "email", "invalid_param"])
            self.assertFalse(res_bad.is_valid)
            self.assertEqual(res_bad.error_code, "UNEXPECTED_KEYWORD_ARG")

            # Test missing required arg
            res_missing = validate_call_site(conn, "create_user", 0, ["username"])
            self.assertFalse(res_missing.is_valid)
            self.assertEqual(res_missing.error_code, "MISSING_REQUIRED_ARG")

            # Test HTML visualizer generation
            html_out = self.workspace / ".omni" / "graph.html"
            generate_graph_html(conn, html_out)
            self.assertTrue(html_out.exists())
            self.assertIn("Omni-Graph Topology", html_out.read_text(encoding="utf-8"))
        finally:
            conn.close()

if __name__ == "__main__":
    unittest.main()
