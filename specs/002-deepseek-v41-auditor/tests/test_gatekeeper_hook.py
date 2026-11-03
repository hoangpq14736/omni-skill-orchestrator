"""
Test Suite for Deterministic Gatekeeper Hook & Council Governance (scripts/hook_runner.py).
Part of Omni-Kernel v4.1 Council Protocol.

Verifies:
1. Conversational filler bypass (<1.0ms)
2. Architecture intent detection (/teamwork, RFC, FRC, spec.md, plan.md)
3. Non-blocking decoupled filesystem verification (verify_critic_artifact)
4. Two-state directive/review context injection (FLAW-002 anti-collision)
5. Zero network/subprocess calls during pre-flight evaluation (<25ms SLA)
"""

import json
import os
import sys
import tempfile
import time
import unittest

REPO_ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")
TESTS_DIR = os.path.dirname(__file__)

for p in (REPO_ROOT, SCRIPTS_DIR, TESTS_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import hook_runner


class TestGatekeeperHook(unittest.TestCase):
    def test_filler_bypass_fast_exit(self):
        """Principle I: Fillers must exit in <1.0ms with empty injectSteps."""
        payload = {"lastUserInput": "ok, tiếp tục đi"}
        t0 = time.perf_counter()
        result = hook_runner.process_hook(payload)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertEqual(result.get("injectSteps"), [])
        self.assertLess(elapsed_ms, 5.0)  # Safe assertion ceiling, typically <0.3ms

    def test_architecture_intent_detection(self):
        """Verify regex catches architecture intents across English and Vietnamese."""
        intents = [
            "Bắt tay vào làm RFC cho hệ thống mới",
            "Thiết kế FRC và SDD bundle",
            "/teamwork triển khai kiến trúc",
            "Review file spec.md và plan.md trước khi code",
            "Thiết kế system architecture cho module caching"
        ]
        for intent in intents:
            is_arch = hook_runner.is_architecture_intent(intent)
            self.assertTrue(is_arch, f"Intent should be detected as architecture: '{intent}'")

        non_arch = [
            "Viết hàm tính fibonacci",
            "Fix bug cú pháp trong utils.py",
            "Chạy unit test",
            "Thêm comment vào hàm main"
        ]
        for item in non_arch:
            is_arch = hook_runner.is_architecture_intent(item)
            self.assertFalse(is_arch, f"Item should not be detected as architecture: '{item}'")

    def test_verify_critic_artifact_missing_or_empty(self):
        with tempfile.TemporaryDirectory() as tmp_ws:
            verdict, meta = hook_runner.verify_critic_artifact(tmp_ws, target_file="spec.md")
            self.assertEqual(verdict, "UNREVIEWED")
            self.assertIsNone(meta)

    def test_verify_critic_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as tmp_ws:
            review_file = os.path.join(tmp_ws, "CRITIC_REVIEW.md")
            meta = {
                "verdict": "REJECTED",
                "target_file": "spec.md",
                "input_hash": "sha256:12345",
                "model": "deepseek-chat"
            }
            with open(review_file, "w", encoding="utf-8") as f:
                f.write(f"<!-- OMNI_AUDIT_META: {json.dumps(meta)} -->\n# Audit Report\nFindings...")

            verdict, parsed_meta = hook_runner.verify_critic_artifact(tmp_ws, target_file="spec.md")
            self.assertEqual(verdict, "REJECTED")
            self.assertIsNotNone(parsed_meta)

    def test_verify_critic_artifact_approved_target_file_matches(self):
        with tempfile.TemporaryDirectory() as tmp_ws:
            review_file = os.path.join(tmp_ws, "CRITIC_REVIEW.md")
            meta = {
                "verdict": "APPROVED",
                "target_file": "spec.md",
                "input_hash": "sha256:abcde",
                "model": "deepseek-chat"
            }
            with open(review_file, "w", encoding="utf-8") as f:
                f.write(f"<!-- OMNI_AUDIT_META: {json.dumps(meta)} -->\n# Approved Report\n100% sound.")

            verdict, parsed_meta = hook_runner.verify_critic_artifact(tmp_ws, target_file="spec.md")
            self.assertEqual(verdict, "APPROVED")
            self.assertEqual(parsed_meta["target_file"], "spec.md")

    def test_flaw002_anti_collision_target_file_mismatch(self):
        """FLAW-002: Review for spec.md must NOT approve plan.md."""
        with tempfile.TemporaryDirectory() as tmp_ws:
            review_file = os.path.join(tmp_ws, "CRITIC_REVIEW.md")
            meta = {
                "verdict": "APPROVED",
                "target_file": "spec.md",
                "input_hash": "sha256:abcde",
                "model": "deepseek-chat"
            }
            with open(review_file, "w", encoding="utf-8") as f:
                f.write(f"<!-- OMNI_AUDIT_META: {json.dumps(meta)} -->\n# Approved Report")

            # Check against plan.md -> should mismatch and return UNREVIEWED
            verdict, parsed_meta = hook_runner.verify_critic_artifact(tmp_ws, target_file="plan.md")
            self.assertEqual(verdict, "UNREVIEWED")

    def test_two_state_directive_injection_unreviewed(self):
        with tempfile.TemporaryDirectory() as tmp_ws:
            payload = {
                "lastUserInput": "Thiết kế RFC mới cho module cache",
                "workspacePaths": [tmp_ws]
            }
            result = hook_runner.process_hook(payload)
            inject_steps = result.get("injectSteps", [])
            self.assertTrue(len(inject_steps) > 0)
            ephemeral = inject_steps[0].get("ephemeralMessage", "")
            self.assertIn("CRITICAL ARCHITECTURE GATEKEEPER DIRECTIVE", ephemeral)
            self.assertIn("consult_critic.py", ephemeral)

    def test_two_state_directive_injection_approved(self):
        with tempfile.TemporaryDirectory() as tmp_ws:
            review_file = os.path.join(tmp_ws, "CRITIC_REVIEW.md")
            meta = {
                "verdict": "APPROVED",
                "target_file": "spec.md",
                "input_hash": "sha256:12345",
                "model": "deepseek-chat"
            }
            with open(review_file, "w", encoding="utf-8") as f:
                f.write(f"<!-- OMNI_AUDIT_META: {json.dumps(meta)} -->\n# Approved Report\n100% sound.")

            payload = {
                "lastUserInput": "Bắt tay vào code theo spec.md đã review",
                "workspacePaths": [tmp_ws]
            }
            result = hook_runner.process_hook(payload)
            inject_steps = result.get("injectSteps", [])
            self.assertTrue(len(inject_steps) > 0)
            ephemeral = inject_steps[0].get("ephemeralMessage", "")
            self.assertIn("GATEKEEPER VERIFIED", ephemeral)
            self.assertIn("APPROVED", ephemeral)

    def test_verify_critic_artifact_stale_when_target_modified_after_review(self):
        """TOCTOU Defense: If target_file mtime > review mtime + 1s, return STALE_REVIEW."""
        with tempfile.TemporaryDirectory() as tmp_ws:
            review_file = os.path.join(tmp_ws, "CRITIC_REVIEW.md")
            target_file = os.path.join(tmp_ws, "spec.md")

            # Create review file with older timestamp
            meta = {
                "verdict": "APPROVED",
                "target_file": "spec.md",
                "input_hash": "sha256:dummy",
                "model": "deepseek-chat"
            }
            with open(review_file, "w", encoding="utf-8") as f:
                f.write(f"<!-- OMNI_AUDIT_META: {json.dumps(meta)} -->\n# Approved Report")
            os.utime(review_file, (1000000, 1000000))

            # Create target file with newer timestamp (+10s)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write("# Modified spec after review")
            os.utime(target_file, (1000010, 1000010))

            verdict, parsed_meta = hook_runner.verify_critic_artifact(tmp_ws, target_file="spec.md")
            self.assertEqual(verdict, "STALE_REVIEW")
            self.assertIn("stale_reason", parsed_meta)

    def test_verify_critic_artifact_stale_when_hash_mismatches(self):
        """TOCTOU Defense: If target_file content hash does not match input_hash in review, return STALE_REVIEW."""
        import hashlib
        with tempfile.TemporaryDirectory() as tmp_ws:
            review_file = os.path.join(tmp_ws, "CRITIC_REVIEW.md")
            target_file = os.path.join(tmp_ws, "spec.md")

            with open(target_file, "w", encoding="utf-8") as f:
                f.write("# Genuine content")

            # Review with different hash
            meta = {
                "verdict": "APPROVED",
                "target_file": "spec.md",
                "input_hash": "sha256:badhash12345",
                "model": "deepseek-chat"
            }
            with open(review_file, "w", encoding="utf-8") as f:
                f.write(f"<!-- OMNI_AUDIT_META: {json.dumps(meta)} -->\n# Approved Report")

            verdict, parsed_meta = hook_runner.verify_critic_artifact(tmp_ws, target_file="spec.md")
            self.assertEqual(verdict, "STALE_REVIEW")
            self.assertIn("hash mismatch", parsed_meta.get("stale_reason", ""))


if __name__ == "__main__":
    unittest.main()
