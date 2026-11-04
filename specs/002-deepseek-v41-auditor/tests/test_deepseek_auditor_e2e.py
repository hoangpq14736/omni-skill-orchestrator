"""
End-to-End Integration & Adversarial Verification Test Suite.
Verifies M4 requirements: Flawed RFC rejection, adversarial defense, fail-closed auth gate,
and live DeepSeek-V4.1-Flash API connectivity.
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
FIXTURES_DIR = os.path.join(TESTS_DIR, "fixtures")
FLAWED_RFC = os.path.join(FIXTURES_DIR, "flawed_rfc.md")

for p in (REPO_ROOT, SCRIPTS_DIR, TESTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from conftest import MockDeepSeekServer


class TestDeepSeekAuditorE2E(unittest.TestCase):
    def setUp(self):
        self.mock_server = MockDeepSeekServer()
        self.base_url = self.mock_server.start()

    def tearDown(self):
        self.mock_server.stop()

    def test_flawed_rfc_end_to_end_audit_and_rejection(self):
        """T034 & T036: Flawed RFC produces REJECTED verdict with >= 3 critical defects."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as out_f:
            out_path = out_f.name

        try:
            cmd = [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "consult_critic.py"),
                "--file", FLAWED_RFC,
                "--out", out_path,
                "--api-base", self.base_url,
                "--timeout", "15"
            ]
            env = os.environ.copy()
            env["DEEPSEEK_API_KEY"] = "sk-test-key-e2e"
            res = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            self.assertEqual(res.returncode, 1, f"Expected exit code 1 for flawed RFC critique, got {res.returncode}")
            self.assertTrue(os.path.exists(out_path))

            with open(out_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Verify line 1 metadata header
            line1 = content.splitlines()[0]
            self.assertTrue(line1.startswith("<!-- OMNI_AUDIT_META: "))
            meta = json.loads(line1.replace("<!-- OMNI_AUDIT_META:", "").replace("-->", "").strip())
            self.assertEqual(meta["verdict"], "REJECTED")
            self.assertEqual(meta["target_file"], "flawed_rfc.md")

            # Verify >= 3 critical vulnerabilities in report
            self.assertIn("Top Critical Architectural Vulnerabilities", content)
            self.assertIn("Raw SQL concatenation", content)
            self.assertIn("Synchronous network call", content)
            self.assertIn("Unredacted API keys", content)

        finally:
            if os.path.exists(out_path):
                os.remove(out_path)

    def test_fail_closed_auth_gate_blocks_echo_chamber_fallback(self):
        """T037: Missing API key exits code 2, fails closed, and strictly blocks echo-chamber fallback."""
        with tempfile.TemporaryDirectory() as empty_dir:
            cmd = [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "consult_critic.py"),
                "--file", FLAWED_RFC
            ]
            env = os.environ.copy()
            env.pop("DEEPSEEK_API_KEY", None)
            res = subprocess.run(
                cmd,
                cwd=empty_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            self.assertEqual(res.returncode, 2, f"Expected fail-closed exit code 2, got {res.returncode}")
            self.assertIn("LỖI XÁC THỰC", res.stderr)
            # Verify no fallback to argon bridge
            self.assertNotIn("consult_argon", res.stderr)
            self.assertNotIn("Argon Bridge", res.stderr)

    def test_live_api_deepseek_connectivity(self):
        """Optional live test against DeepSeek Cloud API if key is present in .env."""
        from consult_critic import load_api_key
        try:
            api_key = load_api_key()
        except SystemExit:
            self.skipTest("No DEEPSEEK_API_KEY configured for live test.")

        if not api_key.startswith("sk-") or api_key == "sk-test-key-e2e":
            self.skipTest("API key is a mock key, skipping live test.")

        # Test live query with 20s timeout budget
        prompt = "Review this minimal architecture: Use SQLite with WAL mode and parameterized SQL."
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "consult_critic.py"),
            "--prompt", prompt,
            "--timeout", "25",
            "--mode", "rfc",
            "--json"
        ]
        t0 = time.monotonic()
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        elapsed = time.monotonic() - t0

        if res.returncode == 3:
            self.skipTest(f"Live DeepSeek API timed out or network rate-limited: {res.stderr}")
        self.assertIn(res.returncode, (0, 1), f"Live DeepSeek request failed with code {res.returncode}. Stderr: {res.stderr}")
        self.assertLess(elapsed, 30.0, f"Turnaround exceeded 30s SLA: {elapsed:.2f}s")
        print(f"\n[+] Live DeepSeek API response in {elapsed:.2f}s! Exit code: {res.returncode}")


if __name__ == "__main__":
    unittest.main()
