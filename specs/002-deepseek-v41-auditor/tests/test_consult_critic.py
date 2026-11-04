"""
Comprehensive Test Suite for Omni-Auditor Strict Architecture Gatekeeper (scripts/consult_critic.py).
Adheres strictly to the Omni-Kernel v4.1 Council Protocol, Draft-07 Conditional Schema,
and Ratified Technical Guardrails (FLAW-001, FLAW-002, FLAW-004).

100% Python Standard Library: unittest, urllib, json, time, os, sys, tempfile, threading.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from typing import Any, Dict

# Ensure repository root and tests directory are in sys.path
REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TESTS_DIR = os.path.dirname(__file__)

for p in (REPO_ROOT, SCRIPTS_DIR, TESTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from conftest import MockDeepSeekServer, make_approved_response
import consult_critic


class TestStrictArgumentParser(unittest.TestCase):
    """Verifies that CLI usage and argument errors strictly exit with code 4."""

    def test_missing_required_arguments_exits_code_4(self):
        cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "consult_critic.py")]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(result.returncode, 4, f"Expected exit code 4 for missing arguments, got {result.returncode}")
        self.assertIn("LỖI THAM SỐ", result.stderr)

    def test_unknown_flag_exits_code_4(self):
        cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "consult_critic.py"), "--invalid-flag-xyz"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(result.returncode, 4, f"Expected exit code 4 for unknown flag, got {result.returncode}")
        self.assertIn("LỖI THAM SỐ", result.stderr)


class TestLoadApiKey(unittest.TestCase):
    """Verifies environment loader and fail-fast behavior with exit code 2."""

    def test_api_key_from_environ(self):
        old_env = os.environ.get("DEEPSEEK_API_KEY")
        try:
            os.environ["DEEPSEEK_API_KEY"] = "sk-test-env-key-12345"
            key = consult_critic.load_api_key()
            self.assertEqual(key, "sk-test-env-key-12345")
        finally:
            if old_env is not None:
                os.environ["DEEPSEEK_API_KEY"] = old_env
            else:
                os.environ.pop("DEEPSEEK_API_KEY", None)

    def test_missing_api_key_exits_code_2(self):
        with tempfile.TemporaryDirectory() as empty_dir:
            cmd = [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "consult_critic.py"),
                "--prompt", "Test prompt"
            ]
            env = os.environ.copy()
            env.pop("DEEPSEEK_API_KEY", None)
            result = subprocess.run(
                cmd,
                cwd=empty_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self.assertEqual(result.returncode, 2, f"Expected exit code 2 for missing API key, got {result.returncode}")
            self.assertIn("LỖI XÁC THỰC", result.stderr)


class TestValidatePath(unittest.TestCase):
    """Verifies path canonicalization, file bounds, and directory traversal defense."""

    def test_valid_file_path(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("# Valid RFC")
            f_path = f.name
        try:
            validated = consult_critic.validate_path(f_path)
            self.assertEqual(os.path.normcase(validated), os.path.normcase(os.path.realpath(f_path)))
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_non_existent_file_exits_code_4(self):
        with self.assertRaises(SystemExit) as ctx:
            consult_critic.validate_path("non_existent_file_xyz_123.md")
        self.assertEqual(ctx.exception.code, 4)

    def test_directory_path_exits_code_4(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(SystemExit) as ctx:
                consult_critic.validate_path(tmp_dir)
            self.assertEqual(ctx.exception.code, 4)

    def test_empty_file_exits_code_4(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f_path = f.name  # 0 bytes
        try:
            with self.assertRaises(SystemExit) as ctx:
                consult_critic.validate_path(f_path)
            self.assertEqual(ctx.exception.code, 4)
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_directory_traversal_outside_allowed_root_exits_code_4(self):
        with tempfile.TemporaryDirectory() as allowed_dir:
            with tempfile.TemporaryDirectory() as forbidden_dir:
                bad_file = os.path.join(forbidden_dir, "secret.md")
                with open(bad_file, "w") as bf:
                    bf.write("secret data")
                with self.assertRaises(SystemExit) as ctx:
                    consult_critic.validate_path(bad_file, allowed_root=allowed_dir)
                self.assertEqual(ctx.exception.code, 4)


class TestSystemPromptAndConditionalSchema(unittest.TestCase):
    """Verifies FLAW-001 conditional vulnerability floor and proof of defense contract."""

    def test_system_prompt_rfc_mode_contains_flaw001_contract(self):
        prompt = consult_critic.build_system_prompt("rfc")
        self.assertIn("PERSONAL PROJECT", prompt)
        self.assertIn("critical_vulnerabilities", prompt)
        self.assertIn("edge_cases", prompt)
        self.assertIn("minItems: 3", prompt)

    def test_validate_audit_verdict_approved_with_zero_vulns_and_3_edge_cases(self):
        data = {
            "verdict": "APPROVED",
            "critical_vulnerabilities": [],
            "edge_cases": [
                {"scenario": "1", "consequence": "a", "mitigation": "m"},
                {"scenario": "2", "consequence": "b", "mitigation": "m"},
                {"scenario": "3", "consequence": "c", "mitigation": "m"},
            ]
        }
        is_valid, msg = consult_critic.validate_audit_verdict(data)
        self.assertTrue(is_valid, f"Expected valid APPROVED verdict, got error: {msg}")

    def test_validate_audit_verdict_approved_with_less_than_3_edge_cases_fails(self):
        data = {
            "verdict": "APPROVED",
            "critical_vulnerabilities": [],
            "edge_cases": [
                {"scenario": "1", "consequence": "a", "mitigation": "m"}
            ]
        }
        is_valid, msg = consult_critic.validate_audit_verdict(data)
        self.assertFalse(is_valid)
        self.assertIn("expected >= 3 edge_cases", msg)

    def test_validate_audit_verdict_approved_with_vulnerabilities_fails(self):
        data = {
            "verdict": "APPROVED",
            "critical_vulnerabilities": [{"id": "V1"}],
            "edge_cases": [{"s": "1"}, {"s": "2"}, {"s": "3"}]
        }
        is_valid, msg = consult_critic.validate_audit_verdict(data)
        self.assertFalse(is_valid)
        self.assertIn("invalid when critical_vulnerabilities > 0", msg)

    def test_validate_audit_verdict_rejected_with_3_vulnerabilities_passes(self):
        data = {
            "verdict": "REJECTED",
            "critical_vulnerabilities": [{"id": "1"}, {"id": "2"}, {"id": "3"}],
            "edge_cases": []
        }
        is_valid, msg = consult_critic.validate_audit_verdict(data)
        self.assertTrue(is_valid)

    def test_validate_audit_verdict_rejected_with_less_than_3_vulnerabilities_fails(self):
        data = {
            "verdict": "REJECTED",
            "critical_vulnerabilities": [{"id": "1"}, {"id": "2"}],
            "edge_cases": []
        }
        is_valid, msg = consult_critic.validate_audit_verdict(data)
        self.assertFalse(is_valid)
        self.assertIn("expected >= 3 critical_vulnerabilities", msg)


class TestBackoffAndFLAW004BudgetAbort(unittest.TestCase):
    """Verifies jittered exponential backoff and FLAW-004 minimum viable inference budget (8.0s)."""

    def test_backoff_bounds(self):
        for attempt in range(3):
            sleep_time = consult_critic.calculate_sleep_duration(attempt)
            self.assertGreaterEqual(sleep_time, 1.0)
            self.assertLessEqual(sleep_time, 10.5)

    def test_flaw004_abort_when_remaining_budget_less_than_8s(self):
        # Remaining budget = 6.0s (< 8.0s) -> sleep clamped to 0.0s, triggers fail-fast in request loop
        deadline = time.monotonic() + 6.0
        sleep_time = consult_critic.calculate_sleep_duration(0, deadline=deadline, min_infer_window=8.0)
        self.assertEqual(sleep_time, 0.0)


class TestEndToEndClientWithMockServer(unittest.TestCase):
    """End-to-End integration tests using ephemeral mock server harness."""

    def setUp(self):
        self.mock_server = MockDeepSeekServer()
        self.base_url = self.mock_server.start()

    def tearDown(self):
        self.mock_server.stop()

    def test_e2e_successful_approved_critique(self):
        # Configure mock server to return APPROVED response
        def approved_handler(handler, req_rec):
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json; charset=utf-8")
            handler.end_headers()
            handler.wfile.write(json.dumps(make_approved_response(3)).encode("utf-8"))

        self.mock_server.set_fallback_handler(approved_handler)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as in_f:
            in_f.write("# Sound Architecture Proposal")
            in_path = in_f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as out_f:
            out_path = out_f.name

        try:
            cmd = [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "consult_critic.py"),
                "--file", in_path,
                "--out", out_path,
                "--api-base", self.base_url,
                "--timeout", "15"
            ]
            env = os.environ.copy()
            env["DEEPSEEK_API_KEY"] = "sk-valid-test-key-12345"
            res = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            self.assertEqual(res.returncode, 0, f"Expected exit code 0 for APPROVED, got {res.returncode}. Stderr: {res.stderr}")
            self.assertTrue(os.path.exists(out_path))

            # Verify FLAW-002: Line 1 metadata comment
            with open(out_path, "r", encoding="utf-8") as rf:
                line1 = rf.readline()

            self.assertTrue(line1.startswith("<!-- OMNI_AUDIT_META: "))
            meta_json = json.loads(line1.replace("<!-- OMNI_AUDIT_META:", "").replace("-->", "").strip())
            self.assertEqual(meta_json["verdict"], "APPROVED")
            self.assertEqual(meta_json["target_file"], os.path.basename(in_path))
            self.assertTrue(meta_json["input_hash"].startswith("sha256:"))

        finally:
            if os.path.exists(in_path): os.remove(in_path)
            if os.path.exists(out_path): os.remove(out_path)

    def test_e2e_rejected_critique_exits_code_1(self):
        # Default mock server returns REJECTED with 3 critical vulns
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as in_f:
            in_f.write("# Flawed Proposal")
            in_path = in_f.name

        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as out_f:
            out_path = out_f.name

        try:
            cmd = [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "consult_critic.py"),
                "--file", in_path,
                "--out", out_path,
                "--api-base", self.base_url,
                "--timeout", "15"
            ]
            env = os.environ.copy()
            env["DEEPSEEK_API_KEY"] = "sk-valid-test-key-12345"
            res = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            self.assertEqual(res.returncode, 1, f"Expected exit code 1 for REJECTED, got {res.returncode}")

            # Verify FLAW-002: Line 1 metadata has REJECTED
            with open(out_path, "r", encoding="utf-8") as rf:
                line1 = rf.readline()
            meta_json = json.loads(line1.replace("<!-- OMNI_AUDIT_META:", "").replace("-->", "").strip())
            self.assertEqual(meta_json["verdict"], "REJECTED")

        finally:
            if os.path.exists(in_path): os.remove(in_path)
            if os.path.exists(out_path): os.remove(out_path)

    def test_e2e_strict_mode_rejection_exits_code_5(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as in_f:
            in_f.write("# Flawed Proposal")
            in_path = in_f.name

        try:
            cmd = [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "consult_critic.py"),
                "--file", in_path,
                "--api-base", self.base_url,
                "--strict",
                "--timeout", "15"
            ]
            env = os.environ.copy()
            env["DEEPSEEK_API_KEY"] = "sk-valid-test-key-12345"
            res = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            self.assertEqual(res.returncode, 5, f"Expected exit code 5 for strict rejection, got {res.returncode}")
            self.assertIn("STRICT MODE REJECTION", res.stderr)

        finally:
            if os.path.exists(in_path): os.remove(in_path)

    def test_e2e_auth_failure_401_exits_code_2(self):
        def auth_fail_handler(handler, req_rec):
            handler.send_response(401)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(b'{"error": {"message": "Invalid API Key"}}')

        self.mock_server.set_fallback_handler(auth_fail_handler)

        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "consult_critic.py"),
            "--prompt", "Review me",
            "--api-base", self.base_url,
            "--timeout", "10"
        ]
        env = os.environ.copy()
        env["DEEPSEEK_API_KEY"] = "sk-bad-key"
        res = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        self.assertEqual(res.returncode, 2, f"Expected exit code 2 on HTTP 401, got {res.returncode}")
        self.assertIn("HTTP 401", res.stderr)

    def test_e2e_billing_failure_402_exits_code_2(self):
        def billing_fail_handler(handler, req_rec):
            handler.send_response(402)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(b'{"error": {"message": "Insufficient Balance"}}')

        self.mock_server.set_fallback_handler(billing_fail_handler)

        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "consult_critic.py"),
            "--prompt", "Review me",
            "--api-base", self.base_url,
            "--timeout", "10"
        ]
        env = os.environ.copy()
        env["DEEPSEEK_API_KEY"] = "sk-key"
        res = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        self.assertEqual(res.returncode, 2, f"Expected exit code 2 on HTTP 402, got {res.returncode}")
        self.assertIn("HTTP 402", res.stderr)

    def test_e2e_credential_redaction_before_transmission(self):
        # Verify that unredacted secrets in prompt are scrubbed before reaching the network
        received_bodies = []

        def recording_handler(handler, req_rec):
            received_bodies.append(req_rec["body"].decode("utf-8"))
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps(make_approved_response(3)).encode("utf-8"))

        self.mock_server.set_fallback_handler(recording_handler)

        leaky_prompt = "Here is my secret token: gsk_1234567890abcdef1234567890 and sk-proj-supersecretkey1234567890"

        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "consult_critic.py"),
            "--prompt", leaky_prompt,
            "--api-base", self.base_url,
            "--timeout", "10"
        ]
        env = os.environ.copy()
        env["DEEPSEEK_API_KEY"] = "sk-key"
        res = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        self.assertEqual(res.returncode, 0)
        self.assertTrue(len(received_bodies) > 0)
        transmitted_text = received_bodies[0]

        self.assertNotIn("gsk_1234567890", transmitted_text)
        self.assertNotIn("sk-proj-supersecretkey", transmitted_text)
        self.assertIn("[REDACTED_GROQ_KEY]", transmitted_text)
        self.assertIn("[REDACTED_OPENAI_KEY]", transmitted_text)


if __name__ == "__main__":
    unittest.main()
