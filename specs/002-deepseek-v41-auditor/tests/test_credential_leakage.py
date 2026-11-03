"""
Security Audit & Credential Leakage Prevention Test Suite.
Verifies Principle II: Zero-Trust Security across all execution paths.

Ensures that API keys, tokens, and private credentials are NEVER leaked to
stdout, stderr, disk review artifacts, or unredacted network requests.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TESTS_DIR = os.path.dirname(__file__)

for p in (REPO_ROOT, SCRIPTS_DIR, TESTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

from conftest import MockDeepSeekServer, make_approved_response
from sanitizer import redact_credentials


class TestCredentialLeakagePrevention(unittest.TestCase):
    def setUp(self):
        self.mock_server = MockDeepSeekServer()
        self.base_url = self.mock_server.start()

    def tearDown(self):
        self.mock_server.stop()

    def test_sanitizer_scrubs_all_credential_types(self):
        test_inputs = [
            ("sk-proj-abc1234567890abcdef1234567890", "[REDACTED_OPENAI_KEY]"),
            ("sk-ant-api03-abcdef1234567890abcdef1234567890", "[REDACTED_ANTHROPIC_KEY]"),
            ("gsk_1234567890abcdef1234567890", "[REDACTED_GROQ_KEY]"),
            ("ghp_123456789012345678901234567890123456", "[REDACTED_GITHUB_TOKEN]"),
            ("github_pat_11ABCD12345678901234567890", "[REDACTED_GITHUB_TOKEN]"),
            ("Bearer my-secret-jwt-token-value-1234567890", "Bearer [REDACTED_BEARER_TOKEN]"),
            ("DEEPSEEK_API_KEY=" + "sk-dummy-test-key-not-real-12345678", "[REDACTED"),
            ("api_key=unquoted_raw_secret_value_12345", 'api_key="[REDACTED]"'),
        ]
        for raw_val, expected_redaction in test_inputs:
            sanitized = redact_credentials(raw_val)
            self.assertIn(expected_redaction, sanitized, f"Failed for {raw_val}")
            # Ensure raw secret is not in sanitized text
            if "=" in raw_val:
                raw_secret = raw_val.split("=", 1)[1]
            elif raw_val.startswith("Bearer "):
                raw_secret = raw_val[7:]
            else:
                raw_secret = raw_val
            self.assertNotIn(raw_secret, sanitized)

    def test_no_credential_leakage_in_consult_critic_execution(self):
        # Configure mock server to record request body
        wire_requests = []

        def capture_handler(handler, req_rec):
            wire_requests.append(req_rec)
            handler.send_response(200)
            handler.send_header("Content-Type", "application/json")
            handler.end_headers()
            handler.wfile.write(json.dumps(make_approved_response(3)).encode("utf-8"))

        self.mock_server.set_fallback_handler(capture_handler)

        secret_token = "sk-proj-supersecretkey9999888877776666"
        leaky_rfc = f"""# Test RFC with Leak
## 1. Secrets
Config: OPENAI_KEY={secret_token}
Authorization: Bearer mylongtoken1234567890abcdef
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as in_f:
            in_f.write(leaky_rfc)
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
                "--timeout", "10"
            ]
            env = os.environ.copy()
            env["DEEPSEEK_API_KEY"] = "sk-live-deepseek-key-12345"
            res = subprocess.run(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Check stdout & stderr
            self.assertNotIn(secret_token, res.stdout, "Secret leaked to stdout!")
            self.assertNotIn(secret_token, res.stderr, "Secret leaked to stderr!")

            # Check persisted artifact
            with open(out_path, "r", encoding="utf-8") as rf:
                artifact_content = rf.read()
            self.assertNotIn(secret_token, artifact_content, "Secret leaked into output artifact!")

            # Check network wire payload
            self.assertTrue(len(wire_requests) > 0)
            wire_body = wire_requests[0]["body"].decode("utf-8")
            self.assertNotIn(secret_token, wire_body, "Secret leaked over the wire!")
            self.assertIn("[REDACTED_OPENAI_KEY]", wire_body)

        finally:
            if os.path.exists(in_path): os.remove(in_path)
            if os.path.exists(out_path): os.remove(out_path)


if __name__ == "__main__":
    unittest.main()
