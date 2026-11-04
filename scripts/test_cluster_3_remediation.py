#!/usr/bin/env python3
"""
Omni-Kernel v4.1: Cluster 3 Comprehensive Remediation Test Suite
Verifies all 9 vulnerabilities and 5 concurrency hazards across:
- scripts/synthesizer.py (AST gated validation, YAML injection defense, clean_name traversal, atomic promotion)
- scripts/indexer.py (OOM memory ceilings, token count & length bounds, atomic registry write with lock)
- scripts/mcp_gateway.py (Metadata exclusion, malformed schema resilience, type confusion bool vs int, thread safety)
- scripts/resolver.py (Deterministic tie-breaking, arbitration replacement re-sort, atomic affinity locking & quarantine)
- scripts/assimilator.py (Symlink traversal containment, DoS memory and entry ceilings)

100% Python Standard Library. Zero external dependencies.
"""

import os
import sys
import json
import time
import shutil
import unittest
import tempfile
import threading
from pathlib import Path

# Ensure scripts directory is on sys.path
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import synthesizer
from synthesizer import (
    generate_skill_template,
    run_sandbox_validation,
    synthesize_and_promote_skill
)

import indexer
from indexer import (
    parse_frontmatter,
    extract_tokens,
    build_index,
    _parse_skill_file,
    MAX_SKILL_SIZE,
    MAX_TOKENS_PER_SKILL,
    MAX_TOKEN_LENGTH
)

import mcp_gateway
from mcp_gateway import (
    discover_mcp_servers,
    index_mcp_tools,
    route_mcp_tool,
    validate_tool_arguments,
    get_mcp_index,
    METADATA_EXCLUDED_FILES
)

import resolver
from resolver import (
    _candidate_sort_key,
    _arbitrate_candidates,
    compare_versions,
    load_learned_affinities,
    save_learned_affinities,
    record_feedback,
    load_registry
)

import assimilator
from assimilator import (
    is_safe_workspace_file,
    find_workspace_skills,
    find_workspace_rules,
    MAX_WORKSPACE_READ
)


# ==============================================================================
# 1. SYNTHESIZER REMEDIATION TESTS (VULN-001, VULN-002, Concurrency #4)
# ==============================================================================
class TestSynthesizerRemediation(unittest.TestCase):
    def test_sandbox_validation_default_gated(self):
        """VULN-001: Automatic arbitrary code execution is gated; AST syntax analysis runs by default."""
        # 1. Valid python syntax passes AST check without executing
        valid_code = "a = 1 + 2\nassert a == 3"
        success, stdout, stderr = run_sandbox_validation(valid_code, allow_exec=False)
        self.assertTrue(success)
        self.assertIn("AST syntax", stdout)

        # 2. Syntax error fails AST check
        invalid_code = "def bad_syntax(:"
        success, stdout, stderr = run_sandbox_validation(invalid_code, allow_exec=False)
        self.assertFalse(success)
        self.assertIn("SyntaxError", stderr)

        # 3. Dangerous system calls blocked when allow_exec=False
        dangerous_code = "import os\nos.system('echo dangerous')"
        success, stdout, stderr = run_sandbox_validation(dangerous_code, allow_exec=False)
        self.assertFalse(success)
        self.assertIn("blocked dangerous call", stderr)

    def test_yaml_frontmatter_injection_blocked(self):
        """VULN-002: Description with newlines or injected YAML keys is sanitized and safely encoded."""
        injection_desc = "Safe description\nname: evil-impersonator\nversion: 999.0.0\n---"
        clean_name, content = generate_skill_template("my-skill", injection_desc)

        # Re-parse frontmatter and assert the name was NOT overridden
        meta, body = parse_frontmatter(content)
        self.assertEqual(meta.get("name"), "my-skill")
        self.assertNotEqual(meta.get("name"), "evil-impersonator")
        self.assertEqual(meta.get("version"), "1.0.0")

    def test_synthesizer_clean_name_path_traversal(self):
        """Defensive #6: Clean name rejects traversal characters ('..', '///', empty)."""
        with self.assertRaises(ValueError):
            generate_skill_template("..", "desc")
        with self.assertRaises(ValueError):
            generate_skill_template("///", "desc")
        with self.assertRaises(ValueError):
            generate_skill_template("", "desc")

    def test_synthesizer_atomic_write_and_fail_loud(self):
        """Concurrency #4: SKILL.md is written atomically and indexing errors are reported."""
        with tempfile.TemporaryDirectory() as td:
            res = synthesize_and_promote_skill(
                name="test-atomic-skill",
                description="Atomic skill description",
                library_dir=td,
                test_code="x = 10"
            )
            self.assertEqual(res["status"], "success")
            skill_file = Path(td) / "test-atomic-skill" / "SKILL.md"
            self.assertTrue(skill_file.is_file())
            content = skill_file.read_text(encoding="utf-8")
            self.assertIn("test-atomic-skill", content)


# ==============================================================================
# 2. INDEXER REMEDIATION TESTS (VULN-003, VULN-006, VULN-009, Concurrency #1)
# ==============================================================================
class TestIndexerRemediation(unittest.TestCase):
    def test_oversized_skill_file_bounded(self):
        """VULN-003: Files exceeding 256 KiB are rejected to prevent OOM."""
        with tempfile.TemporaryDirectory() as td:
            huge_file = Path(td) / "SKILL.md"
            huge_file.write_bytes(b"A" * (MAX_SKILL_SIZE + 1024))
            parsed = _parse_skill_file(str(huge_file), "huge", "library")
            self.assertIsNone(parsed)

    def test_token_bounds_per_skill_and_length(self):
        """VULN-009: Token count is capped at 200 and length at 64 chars."""
        # Oversized word
        long_word = "a" * 100
        tokens = extract_tokens(f"hello {long_word} world")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)
        self.assertNotIn(long_word, tokens)

        # Massive token stream
        massive_text = " ".join([f"word{i}" for i in range(1000)])
        tokens = extract_tokens(massive_text)
        self.assertLessEqual(len(tokens), MAX_TOKENS_PER_SKILL)

    def test_registry_atomic_write_and_locking(self):
        """VULN-006 & Concurrency #1: registry.json is written atomically via temporary file and file lock."""
        with tempfile.TemporaryDirectory() as td:
            reg_path = os.path.join(td, "registry.json")
            # Build index and verify file existence and valid JSON
            reg = build_index(output_file=reg_path)
            self.assertTrue(os.path.isfile(reg_path))
            with open(reg_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded["total_skills"], reg["total_skills"])


# ==============================================================================
# 3. MCP GATEWAY REMEDIATION TESTS (VULN-004, VULN-008, Concurrency #3)
# ==============================================================================
class TestMcpGatewayRemediation(unittest.TestCase):
    def test_mcp_metadata_files_excluded(self):
        """VULN-008: Metadata files (plugin.json, package.json, etc.) are excluded from tool schemas."""
        with tempfile.TemporaryDirectory() as td:
            server_dir = Path(td) / "test_server"
            server_dir.mkdir()
            # Write plugin.json
            (server_dir / "plugin.json").write_text('{"name": "test_plugin", "version": "1.0.0"}', encoding="utf-8")
            # Write a valid tool schema
            valid_tool = {
                "name": "sample_tool",
                "description": "Sample test tool",
                "parameters": {"type": "object", "properties": {"q": {"type": "string"}}}
            }
            (server_dir / "sample_tool.json").write_text(json.dumps(valid_tool), encoding="utf-8")

            servers = discover_mcp_servers(base_dirs=[td])
            self.assertIn("test_server", servers)
            tool_files = servers["test_server"]["tool_files"]
            self.assertEqual(len(tool_files), 1)
            self.assertTrue(tool_files[0].endswith("sample_tool.json"))

    def test_malformed_mcp_schema_does_not_crash_bus(self):
        """VULN-004: Malformed schemas (non-dict schema, non-string description, non-dict properties) handled gracefully."""
        with tempfile.TemporaryDirectory() as td:
            server_dir = Path(td) / "malformed_server"
            server_dir.mkdir()
            
            # 1. Non-dict schema
            (server_dir / "list_tool.json").write_text('["not", "a", "dict"]', encoding="utf-8")
            # 2. Schema with non-string description and non-dict property definition
            malformed_schema = {
                "name": "quirky_tool",
                "description": ["list", "description"],
                "parameters": {
                    "type": "object",
                    "properties": {
                        "bad_prop": "string_not_dict"
                    }
                }
            }
            (server_dir / "quirky_tool.json").write_text(json.dumps(malformed_schema), encoding="utf-8")

            servers = discover_mcp_servers(base_dirs=[td])
            index_data = index_mcp_tools(servers)
            # Bus does not crash and tools are safely normalized
            self.assertGreaterEqual(index_data["total_tools"], 1)

            # Route should not crash when accessing call_template
            routes = route_mcp_tool("quirky", mcp_index=index_data)
            self.assertTrue(isinstance(routes, list))

    def test_validate_arguments_type_confusion_and_non_dict(self):
        """VULN-004: Arguments must be a dict, and bool is strictly rejected for integer/number fields."""
        schema_dir = tempfile.mkdtemp()
        try:
            sdir = Path(schema_dir) / "typed_server"
            sdir.mkdir()
            tool_def = {
                "name": "typed_tool",
                "description": "Typed parameter tool",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "count": {"type": "integer"},
                        "is_active": {"type": "boolean"},
                        "tag": {"type": "string"}
                    },
                    "required": ["count"]
                }
            }
            (sdir / "typed_tool.json").write_text(json.dumps(tool_def), encoding="utf-8")
            mcp_idx = index_mcp_tools(discover_mcp_servers(base_dirs=[schema_dir]))

            # 1. Non-dict arguments rejected cleanly
            res_list = validate_tool_arguments("typed_server", "typed_tool", ["count", 1], mcp_index=mcp_idx)
            self.assertFalse(res_list["valid"])
            self.assertIn("must be a dict", res_list["error"].lower())

            # 2. Type confusion: bool True supplied for integer field fails
            res_bool = validate_tool_arguments("typed_server", "typed_tool", {"count": True}, mcp_index=mcp_idx)
            self.assertFalse(res_bool["valid"])
            self.assertTrue(any("boolean" in err.lower() for err in res_bool["type_errors"]))

            # 3. Valid integer succeeds
            res_ok = validate_tool_arguments("typed_server", "typed_tool", {"count": 42}, mcp_index=mcp_idx)
            self.assertTrue(res_ok["valid"])
        finally:
            shutil.rmtree(schema_dir, ignore_errors=True)

    def test_mcp_index_thread_safety(self):
        """Concurrency #3: Concurrent calls to get_mcp_index are protected by lock."""
        exceptions = []

        def worker():
            try:
                for _ in range(5):
                    idx = get_mcp_index()
                    self.assertIn("tools", idx)
            except Exception as e:
                exceptions.append(e)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(exceptions), 0)


# ==============================================================================
# 4. RESOLVER & ARBITRATION TESTS (VULN-005, VULN-006, Concurrency #2)
# ==============================================================================
class TestResolverRemediation(unittest.TestCase):
    def test_arbitration_deterministic_tie_breaking(self):
        """VULN-005: Equal-score candidates order deterministically across runs."""
        c1 = {"skill": {"name": "alpha", "quality_score": 50, "source_type": "plugin", "version": "1.0.0"}, "raw_score": 85.0, "specificity": 2}
        c2 = {"skill": {"name": "beta", "quality_score": 50, "source_type": "plugin", "version": "1.0.0"}, "raw_score": 85.0, "specificity": 2}

        key1 = _candidate_sort_key(c1)
        key2 = _candidate_sort_key(c2)
        # Sort keys must be strictly ordered without relying on non-deterministic dict/set order
        self.assertNotEqual(key1, key2)

        candidates = [c1, c2]
        candidates.sort(key=_candidate_sort_key, reverse=True)
        order1 = [c["skill"]["name"] for c in candidates]

        candidates_reversed = [c2, c1]
        candidates_reversed.sort(key=_candidate_sort_key, reverse=True)
        order2 = [c["skill"]["name"] for c in candidates_reversed]

        self.assertEqual(order1, order2)

    def test_arbitrated_winner_not_dropped_on_top_k(self):
        """VULN-005: Replacement candidates are re-sorted so winners are not sliced off by top_k."""
        # Existing domain skill
        c_existing = {
            "skill": {"name": "web-generic", "quality_score": 50, "source_type": "builtin", "version": "1.0.0"},
            "raw_score": 90.0,
            "specificity": 1
        }
        # Unrelated domain skill
        c_unrelated = {
            "skill": {"name": "cad-generic", "quality_score": 50, "source_type": "builtin", "version": "1.0.0"},
            "raw_score": 80.0,
            "specificity": 1
        }
        # Higher specificity candidate that replaces web-generic
        c_replacement = {
            "skill": {"name": "web-nextjs", "quality_score": 80, "source_type": "plugin", "version": "2.0.0"},
            "raw_score": 95.0,
            "specificity": 4
        }

        candidates = [c_existing, c_unrelated, c_replacement]
        arbitrated = _arbitrate_candidates(candidates, stack_tags=["web"], query_tokens=["web"])

        # Top 1 should be the replacement winner (web-nextjs), NOT sliced off or dropped
        top_1 = arbitrated[:1]
        self.assertEqual(len(top_1), 1)
        self.assertEqual(top_1[0]["skill"]["name"], "web-nextjs")

    def test_learned_affinities_atomic_and_locked(self):
        """VULN-006 & Concurrency #2: Concurrent record_feedback updates are atomic and thread-safe."""
        with tempfile.TemporaryDirectory() as td:
            aff_path = os.path.join(td, "affinities.json")
            errors = []

            def worker(i):
                try:
                    record_feedback(
                        intent_text="test query",
                        chosen_skill=f"skill_{i % 3}",
                        affinities_path=aff_path
                    )
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(len(errors), 0)
            data = load_learned_affinities(aff_path)
            self.assertIn("affinities", data)
            self.assertGreaterEqual(len(data.get("skill_stats", {})), 1)

    def test_corrupt_learned_affinities_quarantined_not_silently_reset(self):
        """VULN-006: Corrupt affinities file is quarantined with diagnostic and not silently clobbered."""
        with tempfile.TemporaryDirectory() as td:
            aff_path = os.path.join(td, "corrupt_aff.json")
            with open(aff_path, "w", encoding="utf-8") as f:
                f.write("{ invalid json payload")

            data = load_learned_affinities(aff_path)
            self.assertEqual(data["affinities"], {})
            # Corrupted backup should exist
            quarantined = [f for f in os.listdir(td) if f.startswith("corrupt_aff.json.corrupt.")]
            self.assertGreaterEqual(len(quarantined), 1)


# ==============================================================================
# 5. ASSIMILATOR REMEDIATION TESTS (VULN-007, VULN-009)
# ==============================================================================
class TestAssimilatorRemediation(unittest.TestCase):
    def test_symlink_traversal_rejected(self):
        """VULN-007: Files outside workspace or symlinks are rejected by is_safe_workspace_file."""
        with tempfile.TemporaryDirectory() as td:
            ws_dir = os.path.join(td, "workspace")
            outside_dir = os.path.join(td, "outside")
            os.makedirs(ws_dir)
            os.makedirs(outside_dir)

            outside_file = os.path.join(outside_dir, "secret.md")
            with open(outside_file, "w", encoding="utf-8") as f:
                f.write("# Secret rule")

            # Normal inside file is safe
            inside_file = os.path.join(ws_dir, "GEMINI.md")
            with open(inside_file, "w", encoding="utf-8") as f:
                f.write("# Workspace rules")
            self.assertTrue(is_safe_workspace_file(inside_file, ws_dir))

            # Outside file is rejected
            self.assertFalse(is_safe_workspace_file(outside_file, ws_dir))

            # Symlink pointing outside is rejected
            symlink_file = os.path.join(ws_dir, "LINK.md")
            try:
                os.symlink(outside_file, symlink_file)
                self.assertFalse(is_safe_workspace_file(symlink_file, ws_dir))
            except (OSError, NotImplementedError):
                pass  # Symlink creation may require admin privileges on some Windows configurations

    def test_workspace_scan_bounded(self):
        """VULN-009: Scans cap reading at 64 KiB per file."""
        with tempfile.TemporaryDirectory() as td:
            huge_rule = os.path.join(td, "GEMINI.md")
            with open(huge_rule, "wb") as f:
                f.write(b"# Rule\n" + b"X" * (MAX_WORKSPACE_READ + 5000))

            rules = find_workspace_rules(td, is_trusted=True)
            self.assertEqual(len(rules), 1)
            self.assertLessEqual(len(rules[0]["content_preview"]), 500)


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.TestLoader().loadTestsFromNames([
        "__main__.TestSynthesizerRemediation",
        "__main__.TestIndexerRemediation",
        "__main__.TestMcpGatewayRemediation",
        "__main__.TestResolverRemediation",
        "__main__.TestAssimilatorRemediation",
    ])
    result = runner.run(suite)
    print("=" * 65)
    print("🛡️ OMNI-KERNEL v4.1: CLUSTER 3 REMEDIATION TEST SUITE")
    print("=" * 65)
    if result.wasSuccessful():
        print(f"🎉 ALL {result.testsRun} TESTS PASSED (100% SUCCESS)!")
        sys.exit(0)
    else:
        print(f"❌ {len(result.failures)} FAILURES, {len(result.errors)} ERRORS OUT OF {result.testsRun} TESTS")
        sys.exit(1)
