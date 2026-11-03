"""
Test Suite for DeepSeek Virtual MCP Server Driver (deepseek_worker_mcp.py).
Verifies JSON-RPC 2.0 stdio protocol, tool schemas, execution, and graceful exit.

100% Python Standard Library: unittest, subprocess, json, sys, os, tempfile.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TESTS_DIR = os.path.dirname(__file__)
MCP_SERVER_DIR = r"d:\Antigravity\DeepSeek Worker"
MCP_SERVER_PATH = os.path.join(MCP_SERVER_DIR, "deepseek_worker_mcp.py")

for p in (REPO_ROOT, SCRIPTS_DIR, TESTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from conftest import MockDeepSeekServer, make_approved_response


class TestDeepSeekMCPDriver(unittest.TestCase):
    def setUp(self):
        self.mock_server = MockDeepSeekServer()
        self.base_url = self.mock_server.start()

    def tearDown(self):
        self.mock_server.stop()

    def _start_mcp_process(self, extra_env=None):
        env = os.environ.copy()
        env["DEEPSEEK_API_KEY"] = "sk-test-mcp-key-12345"
        env["DEEPSEEK_API_BASE"] = self.base_url
        env["PYTHONUNBUFFERED"] = "1"
        if extra_env:
            env.update(extra_env)

        proc = subprocess.Popen(
            [sys.executable, MCP_SERVER_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=env
        )
        return proc

    def test_mcp_server_initialize_and_tools_list(self):
        proc = self._start_mcp_process()
        try:
            # 1. Initialize
            init_req = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"}
                }
            }
            proc.stdin.write(json.dumps(init_req) + "\n")
            proc.stdin.flush()
            init_resp = json.loads(proc.stdout.readline())

            self.assertEqual(init_resp.get("jsonrpc"), "2.0")
            self.assertEqual(init_resp.get("id"), 1)
            self.assertIn("capabilities", init_resp.get("result", {}))
            self.assertEqual(init_resp["result"]["serverInfo"]["name"], "deepseek_worker_cloud")

            # 2. tools/list
            list_req = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }
            proc.stdin.write(json.dumps(list_req) + "\n")
            proc.stdin.flush()
            list_resp = json.loads(proc.stdout.readline())

            self.assertEqual(list_resp.get("id"), 2)
            tools = list_resp.get("result", {}).get("tools", [])
            tool_names = [t.get("name") for t in tools]
            self.assertIn("deepseek_audit_spec", tool_names)
            self.assertIn("deepseek_audit_diff", tool_names)

        finally:
            proc.stdin.close()
            proc.wait(timeout=3.0)

    def test_mcp_unknown_tool_returns_jsonrpc_error(self):
        proc = self._start_mcp_process()
        try:
            req = {
                "jsonrpc": "2.0",
                "id": 99,
                "method": "tools/call",
                "params": {
                    "name": "non_existent_tool_xyz",
                    "arguments": {}
                }
            }
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()
            resp = json.loads(proc.stdout.readline())

            self.assertEqual(resp.get("id"), 99)
            self.assertIn("error", resp)
            self.assertEqual(resp["error"]["code"], -32601)
        finally:
            proc.stdin.close()
            proc.wait(timeout=3.0)

    def test_mcp_call_deepseek_audit_spec(self):
        # Configure mock server to return APPROVED response
        def approved_handler(handler, req_rec):
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json; charset=utf-8")
            handler.end_headers()
            handler.wfile.write(json.dumps(make_approved_response(3)).encode("utf-8"))

        self.mock_server.set_fallback_handler(approved_handler)

        proc = self._start_mcp_process()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tf:
            tf.write("# Architectural Spec for MCP Test")
            spec_path = tf.name

        try:
            req = {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "deepseek_audit_spec",
                    "arguments": {
                        "spec_file": spec_path,
                        "mode": "rfc"
                    }
                }
            }
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()
            resp = json.loads(proc.stdout.readline())

            self.assertEqual(resp.get("id"), 10)
            self.assertIn("result", resp)
            content_list = resp["result"].get("content", [])
            self.assertTrue(len(content_list) > 0)
            text_data = content_list[0].get("text", "")
            res_json = json.loads(text_data)
            self.assertEqual(res_json.get("verdict"), "APPROVED")
            self.assertEqual(res_json.get("success"), True)
        finally:
            if os.path.exists(spec_path):
                os.remove(spec_path)
            proc.stdin.close()
            proc.wait(timeout=3.0)

    def test_mcp_call_deepseek_audit_diff(self):
        def approved_handler(handler, req_rec):
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json; charset=utf-8")
            handler.end_headers()
            handler.wfile.write(json.dumps(make_approved_response(3)).encode("utf-8"))

        self.mock_server.set_fallback_handler(approved_handler)

        proc = self._start_mcp_process()
        try:
            req = {
                "jsonrpc": "2.0",
                "id": 20,
                "method": "tools/call",
                "params": {
                    "name": "deepseek_audit_diff",
                    "arguments": {
                        "diff_text": "--- a/test.py\n+++ b/test.py\n@@ -1 +1 @@\n-old\n+new"
                    }
                }
            }
            proc.stdin.write(json.dumps(req) + "\n")
            proc.stdin.flush()
            resp = json.loads(proc.stdout.readline())

            self.assertEqual(resp.get("id"), 20)
            self.assertIn("result", resp)
            content_list = resp["result"].get("content", [])
            self.assertTrue(len(content_list) > 0)
            text_data = content_list[0].get("text", "")
            res_json = json.loads(text_data)
            self.assertEqual(res_json.get("verdict"), "APPROVED")
        finally:
            proc.stdin.close()
            proc.wait(timeout=3.0)


if __name__ == "__main__":
    unittest.main()
