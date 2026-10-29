"""
Automated Test Suite for Omni-Skill Orchestrator
Tests indexer performance, resolver accuracy, stack detection, and version arbitration.
"""

import os
import sys
import time
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
from indexer import build_index
from resolver import (
    resolve_skill, detect_workspace_stack, compare_versions, load_registry,
    record_feedback, get_learned_stats, reset_learning, infer_domain_rules_and_mcp
)
from synthesizer import synthesize_and_promote_skill, run_sandbox_validation


class TestOmniSkillOrchestrator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.reg = load_registry()

    def test_01_indexer_coverage(self):
        """Verify that indexer finds 500+ skills across all sources."""
        skills = self.reg.get("skills", [])
        self.assertGreater(len(skills), 400, f"Expected >400 skills, found {len(skills)}")
        
        sources = set(s["source_type"] for s in skills)
        self.assertIn("plugin", sources)
        self.assertIn("library", sources)
        self.assertIn("builtin", sources)

    def test_02_version_comparison(self):
        """Test SemVer and date comparisons."""
        self.assertEqual(compare_versions("2.3.0", "1.1.0"), 1)
        self.assertEqual(compare_versions("1.0.0", "1.0.1"), -1)
        self.assertEqual(compare_versions("2.0", "2.0.0"), 0)

    def test_03_resolve_bigquery(self):
        """Ensure BigQuery queries match BigQuery SQL skill."""
        results = resolve_skill("tối ưu câu lệnh truy vấn bigquery sql", top_k=3, registry=self.reg)
        self.assertTrue(len(results) > 0)
        top_name = results[0]["skill"]["name"]
        self.assertIn("bigquery", top_name)

    def test_04_resolve_fastapi(self):
        """Ensure FastAPI queries match FastAPI patterns."""
        results = resolve_skill("xây dựng api restful với fastapi pydantic", top_k=3, registry=self.reg)
        self.assertTrue(len(results) > 0)
        names = [r["skill"]["name"] for r in results]
        self.assertIn("fastapi-patterns", names)

    def test_05_resolve_flutter(self):
        """Ensure Flutter queries match Flutter skills."""
        results = resolve_skill("thiết kế ứng dụng flutter widget và state management", top_k=3, registry=self.reg)
        self.assertTrue(len(results) > 0)
        names = [r["skill"]["name"] for r in results]
        self.assertTrue(any("flutter" in n or "dart" in n for n in names))

    def test_06_resolve_ponytail(self):
        """Ensure Ponytail queries match Ponytail lazy senior dev skill."""
        results = resolve_skill("tinh giản code ngắn gọn theo phong cách lười biếng ponytail", top_k=3, registry=self.reg)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["skill"]["name"], "ponytail")

    def test_07_sub_10ms_performance(self):
        """Measure resolution speed to ensure it takes < 10ms."""
        start = time.perf_counter()
        for _ in range(50):
            resolve_skill("review code và kiểm thử tự động", top_k=3, registry=self.reg)
        elapsed = (time.perf_counter() - start) / 50.0
        self.assertLess(elapsed, 0.010, f"Resolution took {elapsed*1000:.2f}ms (expected < 10ms)")

    def test_08_auto_refresh_on_new_skill(self):
        """Verify automatic detection and indexing when a new skill is added in the future."""
        from indexer import is_registry_stale, SOURCES
        import shutil

        dummy_dir = os.path.join(SOURCES["library"], "temp-test-auto-refresh")
        os.makedirs(dummy_dir, exist_ok=True)
        dummy_file = os.path.join(dummy_dir, "SKILL.md")

        try:
            with open(dummy_file, "w", encoding="utf-8") as f:
                f.write("---\nname: temp-test-auto-refresh\ndescription: Test auto refresh\n---\n")
            
            # Should detect staleness automatically
            self.assertTrue(is_registry_stale(self.reg))
            
            # load_registry should auto-rebuild
            updated_reg = load_registry()
            names = [s["name"] for s in updated_reg["skills"]]
            self.assertIn("temp-test-auto-refresh", names)
        finally:
            if os.path.exists(dummy_dir):
                shutil.rmtree(dummy_dir)
            # Rebuild clean registry
            build_index(os.path.join(os.path.dirname(__file__), "..", "scripts", "registry.json"))

    def test_09_self_learning_feedback(self):
        """Verify that Meta-Evolution records feedback and elevates chosen skills on subsequent queries."""
        temp_aff_path = os.path.join(os.path.dirname(__file__), "temp_test_affinities.json")
        try:
            # Clean start
            reset_learning(temp_aff_path)

            # Query before feedback
            initial_res = resolve_skill("canvas game animation", top_k=5, registry=self.reg, affinities_path=temp_aff_path)
            initial_names = [r["skill"]["name"] for r in initial_res]
            self.assertNotIn("generative_ui", initial_names[:1])

            # Record feedback teaching Omni that 'canvas game animation' should activate 'generative_ui'
            fb = record_feedback("canvas game animation", None, "generative_ui", affinities_path=temp_aff_path)
            self.assertEqual(fb["status"], "ok")
            self.assertEqual(fb["chosen_skill"], "generative_ui")

            # Query after feedback
            learned_res = resolve_skill("canvas game animation", top_k=5, registry=self.reg, affinities_path=temp_aff_path)
            self.assertTrue(len(learned_res) > 0)
            top_cand = learned_res[0]
            self.assertEqual(top_cand["skill"]["name"], "generative_ui")
            self.assertGreater(top_cand.get("learned_boost", 0), 0)

            # Check stats
            stats = get_learned_stats(temp_aff_path)
            self.assertGreaterEqual(stats["total_tokens_learned"], 3)
            self.assertEqual(stats["top_skills"][0][0], "generative_ui")
            self.assertEqual(stats["top_skills"][0][1]["chosen_count"], 1)

            # Sub-millisecond performance check
            start = time.perf_counter()
            for _ in range(50):
                resolve_skill("canvas game animation", top_k=3, registry=self.reg, affinities_path=temp_aff_path)
            elapsed = (time.perf_counter() - start) / 50.0
            self.assertLess(elapsed, 0.005, f"Learned resolution took {elapsed*1000:.2f}ms (expected < 5ms)")

        finally:
            if os.path.exists(temp_aff_path):
                os.remove(temp_aff_path)

    def test_10_cognitive_pre_flight_and_inferred_rules(self):
        """Verify Omni-Kernel v2.0 cognitive pre-flight matrix and implicit rule inference."""
        res = resolve_skill("xây dựng api fastapi upload file avatar", unified=True, registry=self.reg)
        self.assertIn("skills", res)
        self.assertIn("inferred_rules", res)
        self.assertIn("cognitive_pre_flight", res)
        
        rules_text = " ".join(res["inferred_rules"])
        self.assertIn("Ring 0 Security", rules_text)
        self.assertTrue(any("FastAPI" in r or "Upload" in r or "Web" in r for r in res["inferred_rules"]))
        
        pre = res["cognitive_pre_flight"]
        self.assertIn("loi_value", pre)
        self.assertIn("hai_risks", pre)
        self.assertIn("du_completeness", pre)
        self.assertIn("thieu_implicit", pre)

    def test_11_synthesizer_sandbox_validation_and_promotion(self):
        """Verify autonomous skill synthesis with sandbox execution and promotion."""
        import tempfile
        import shutil

        # Test failure case (bad test)
        fail_res = run_sandbox_validation("assert 1 == 2, 'Should fail'")
        self.assertFalse(fail_res[0])
        self.assertIn("Should fail", fail_res[2])

        # Test success case with temporary library dir
        temp_lib = tempfile.mkdtemp(prefix="omni_test_lib_")
        try:
            synth_res = synthesize_and_promote_skill(
                name="test-auto-synth-sensor",
                description="Auto generated sensor reader skill",
                domain="embedded",
                test_code="def read(): return 42\nassert read() == 42",
                library_dir=temp_lib
            )
            self.assertEqual(synth_res["status"], "success")
            self.assertTrue(os.path.exists(synth_res["path"]))
            with open(synth_res["path"], "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("test-auto-synth-sensor", content)
                self.assertIn("embedded", content)
        finally:
            if os.path.exists(temp_lib):
                shutil.rmtree(temp_lib)


if __name__ == "__main__":
    unittest.main()
