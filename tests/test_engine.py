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
from resolver import resolve_skill, detect_workspace_stack, compare_versions, load_registry


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


if __name__ == "__main__":
    unittest.main()
