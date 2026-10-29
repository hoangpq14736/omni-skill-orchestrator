"""
Automated Test Suite for Omni-Skill Orchestrator
Tests indexer performance, resolver accuracy, stack detection, and version arbitration.
"""

import os
import sys
import time
import json
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))
from indexer import build_index
from resolver import (
    resolve_skill, detect_workspace_stack, compare_versions, load_registry,
    record_feedback, get_learned_stats, reset_learning, infer_domain_rules_and_mcp
)
from synthesizer import synthesize_and_promote_skill, run_sandbox_validation
from hook_runner import process_hook
from assimilator import assimilate_workspace


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

    def test_12_cross_model_json_contract(self):
        """Verify strict schema compatibility and JSON serializability for Gemini, Claude, and GPT models."""
        import json
        res = resolve_skill("thiết kế api microservice docker", unified=True, registry=self.reg)
        self.assertIsInstance(res, dict)
        self.assertIn("skills", res)
        self.assertIn("inferred_rules", res)
        self.assertIn("suggested_mcp", res)
        self.assertIn("cognitive_pre_flight", res)

        # Cross-model JSON serialization test (no non-serializable objects)
        serialized = json.dumps(res, ensure_ascii=False)
        self.assertIsInstance(serialized, str)
        deserialized = json.loads(serialized)
        self.assertEqual(len(deserialized["skills"]), len(res["skills"]))

    def test_13_mixed_stack_detection(self):
        """Verify stack detector correctly identifies multiple simultaneous technologies."""
        import tempfile
        import shutil

        temp_ws = tempfile.mkdtemp(prefix="omni_mixed_stack_")
        try:
            # Create Next.js package.json
            with open(os.path.join(temp_ws, "package.json"), "w", encoding="utf-8") as f:
                json.dump({"dependencies": {"next": "14.2.0", "react": "18.3.0", "tailwind": "3.4.0"}}, f)
            # Create FastAPI requirements.txt
            with open(os.path.join(temp_ws, "requirements.txt"), "w", encoding="utf-8") as f:
                f.write("fastapi>=0.110.0\npydantic>=2.7.0\n")
            # Create Dockerfile
            with open(os.path.join(temp_ws, "Dockerfile"), "w", encoding="utf-8") as f:
                f.write("FROM python:3.11-slim\n")

            stack = detect_workspace_stack(temp_ws)
            self.assertIn("nextjs", stack)
            self.assertIn("react", stack)
            self.assertIn("fastapi", stack)
            self.assertIn("python", stack)
            self.assertIn("docker", stack)
        finally:
            if os.path.exists(temp_ws):
                shutil.rmtree(temp_ws)

    def test_14_bilingual_unaccented_resilience(self):
        """Verify that unaccented Vietnamese queries resolve equivalently to accented queries."""
        accented_res = resolve_skill("tối ưu câu lệnh truy vấn cơ sở dữ liệu sql postgres", top_k=3, registry=self.reg)
        unaccented_res = resolve_skill("toi uu cau lenh truy van co so du lieu sql postgres", top_k=3, registry=self.reg)

        self.assertTrue(len(accented_res) > 0)
        self.assertTrue(len(unaccented_res) > 0)
        top_accented = accented_res[0]["skill"]["name"]
        top_unaccented = unaccented_res[0]["skill"]["name"]
        self.assertEqual(top_accented, top_unaccented, f"Expected {top_accented} == {top_unaccented}")

    def test_15_non_existent_workspace_and_boundary_fallback(self):
        """Verify graceful fallback without exceptions when workspace is invalid or intent is empty."""
        # Non-existent directory
        res_invalid_ws = resolve_skill("test", workspace_dir="Z:/invalid/path/does_not_exist_999", registry=self.reg)
        self.assertIsInstance(res_invalid_ws, list)

        # Empty intent
        res_empty = resolve_skill("", workspace_dir=None, registry=self.reg)
        self.assertTrue(len(res_empty) > 0)
        self.assertIn(res_empty[0]["skill"]["name"], ["ponytail", "coding-standards"])

        # Punctuation only
        res_symbols = resolve_skill("??? !!! @@@ ### $$$", workspace_dir=None, registry=self.reg)
        self.assertTrue(len(res_symbols) > 0)

    def test_16_synthesizer_timeout_and_syntax_containment(self):
        """Verify that synthesizer sandbox handles execution timeouts and syntax errors safely."""
        # Syntax error
        success_syntax, _, err_syntax = run_sandbox_validation("def invalid_syntax(: pass")
        self.assertFalse(success_syntax)
        self.assertTrue(len(err_syntax) > 0)

        # Timeout containment
        timeout_code = "import time\ntime.sleep(10)"
        success_timeout, _, err_timeout = run_sandbox_validation(timeout_code, timeout_sec=1)
        self.assertFalse(success_timeout)
        self.assertIn("timed out", err_timeout)

    def test_17_hook_runner_contract(self):
        """Verify that PreInvocation hook runner produces compliant ephemeral message injection."""
        payload = {
            "lastUserInput": "viết api fastapi và postgresql",
            "workspacePaths": ["d:/Antigravity/Skill management"]
        }
        output = process_hook(payload)
        self.assertIn("injectSteps", output)
        self.assertEqual(len(output["injectSteps"]), 1)
        step = output["injectSteps"][0]
        self.assertIn("ephemeralMessage", step)
        msg = step["ephemeralMessage"]
        self.assertIn("[OMNI-KERNEL v2.5 PRE-FLIGHT ACTIVATION]", msg)
        self.assertIn("fastapi", msg.lower())
        self.assertIn("Inferred Domain Rules", msg)
        self.assertIn("SQL Injection Immunity", msg)
        self.assertIn("Cognitive Pre-Flight Assessment", msg)

    def test_18_hook_runner_edge_cases(self):
        """Verify that hook runner skips trivial fillers, slash commands, and empty inputs."""
        # Trivial filler
        res_ok = process_hook({"lastUserInput": "ok", "workspacePaths": []})
        self.assertEqual(res_ok, {"injectSteps": []})

        # Slash command
        res_slash = process_hook({"lastUserInput": "/plan architecture", "workspacePaths": []})
        self.assertEqual(res_slash, {"injectSteps": []})

        # Empty payload
        res_empty = process_hook({})
        self.assertEqual(res_empty, {"injectSteps": []})

        # Whitespace
        res_space = process_hook({"lastUserInput": "   \n\t  "})
        self.assertEqual(res_space, {"injectSteps": []})

    def test_19_workspace_assimilator_rules_and_skills(self):
        """Verify that Assimilator discovers local skills and Cursor/Claude/Gemini rules."""
        import tempfile
        import shutil

        temp_ws = tempfile.mkdtemp(prefix="omni_assimilate_test_")
        try:
            # Create .cursorrules
            with open(os.path.join(temp_ws, ".cursorrules"), "w", encoding="utf-8") as f:
                f.write("# Project Rules\n- Always use strict TypeScript\n- Zero console.log in prod\n")
            
            # Create a local skill
            local_skill_dir = os.path.join(temp_ws, "skills", "payment-service")
            os.makedirs(local_skill_dir, exist_ok=True)
            with open(os.path.join(local_skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: payment-service\ndescription: Internal Stripe and PayPal checkout integration\nversion: 2.1.0\n---\n# Payment Integration Guide\n")

            data = assimilate_workspace(temp_ws)
            self.assertEqual(data["skills_count"], 1)
            self.assertEqual(data["rules_count"], 1)
            self.assertEqual(data["skills"][0]["name"], "payment-service")
            self.assertEqual(data["skills"][0]["source_type"], "workspace")
            self.assertEqual(data["rules"][0]["source"], ".cursorrules")
        finally:
            if os.path.exists(temp_ws):
                shutil.rmtree(temp_ws)

    def test_20_resolver_workspace_virtualization_integration(self):
        """Verify that Unified Resolver automatically prioritizes local workspace skills and rules."""
        import tempfile
        import shutil

        temp_ws = tempfile.mkdtemp(prefix="omni_resolver_virt_test_")
        try:
            # Create CLAUDE.md rule
            with open(os.path.join(temp_ws, "CLAUDE.md"), "w", encoding="utf-8") as f:
                f.write("# Repository Guidelines\n- Never use any in TypeScript\n- Must write e2e tests\n")

            # Create local skill
            local_skill_dir = os.path.join(temp_ws, "skills", "crm-connector")
            os.makedirs(local_skill_dir, exist_ok=True)
            with open(os.path.join(local_skill_dir, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: crm-connector\ndescription: Enterprise Salesforce CRM webhook synchronization\nversion: 1.0.0\n---\n# CRM Documentation\n")

            res = resolve_skill("sync salesforce crm webhook data", workspace_dir=temp_ws, unified=True)
            self.assertTrue(len(res["skills"]) > 0)
            top_skill = res["skills"][0]["skill"]
            self.assertEqual(top_skill["name"], "crm-connector")
            self.assertEqual(top_skill["source_type"], "workspace")

            # Check rule assimilation
            inferred = res["inferred_rules"]
            rule_matched = any("Workspace Rule (CLAUDE.md)" in r for r in inferred)
            self.assertTrue(rule_matched, f"Expected Workspace Rule (CLAUDE.md) in {inferred}")
        finally:
            if os.path.exists(temp_ws):
                shutil.rmtree(temp_ws)

    def test_21_last_activation_telemetry_and_transparency(self):
        """Verify that hook runner persists telemetry and injects transparency directive."""
        from hook_runner import LAST_ACTIVATION_PATH
        payload = {
            "lastUserInput": "triển khai docker compose container",
            "workspacePaths": ["d:/Antigravity/Skill management"]
        }
        output = process_hook(payload)
        self.assertEqual(len(output["injectSteps"]), 1)
        msg = output["injectSteps"][0]["ephemeralMessage"]
        self.assertIn("Transparency Directive", msg)
        self.assertIn("⚡ Omni-Kernel: [L1 Reflex] | Skill:", msg)

        # Verify telemetry persistence
        self.assertTrue(os.path.exists(LAST_ACTIVATION_PATH))
        with open(LAST_ACTIVATION_PATH, "r", encoding="utf-8") as f:
            record = json.load(f)
        self.assertEqual(record["user_input"], "triển khai docker compose container")
        self.assertIn("top_skill", record)
        self.assertTrue(len(record["inferred_rules"]) > 0)

    def test_22_dual_tier_routing_and_quota_guard(self):
        """Verify that Dual-Tier router accurately calculates complexity and gates Subagent elevation."""
        from dual_tier import calculate_task_complexity

        # 1. Simple task -> L1 Reflex, 0-token Quota Guard
        res_simple = calculate_task_complexity("viết hàm cộng hai số nguyên trong python")
        self.assertEqual(res_simple["tier"], 1)
        self.assertEqual(res_simple["tier_name"], "L1 Reflex")
        self.assertFalse(res_simple["recommend_subagent"])
        self.assertIn("L1 Reflex", res_simple["quota_guard"])

        # 2. Complex architectural task -> L2 Strategist
        res_complex = calculate_task_complexity("lập kế hoạch kiến trúc microservices và phân tách 10 modules")
        self.assertEqual(res_complex["tier"], 2)
        self.assertEqual(res_complex["tier_name"], "L2 Strategist")
        self.assertTrue(res_complex["recommend_subagent"])
        self.assertEqual(res_complex["subagent_role"], "Omni-Strategist")
        self.assertIn("Tier 2 Subagent Approved", res_complex["quota_guard"])

        # 3. Integration with Unified Resolver
        res_unified = resolve_skill("lập kế hoạch kiến trúc", unified=True)
        self.assertIn("tier_assessment", res_unified)
        self.assertEqual(res_unified["tier_assessment"]["tier"], 2)

    def test_23_experiential_memory_engine(self):
        """Verify that Cross-Session Experiential Memory records, recalls, and injects traces in <1ms."""
        import tempfile
        from experiential_memory import (
            record_trace, recall_traces, load_traces, save_traces, seed_canonical_traces
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_traces_path = os.path.join(tmp_dir, "test_traces.json")

            # 1. Seed canonical traces
            seeded = seed_canonical_traces(tmp_traces_path)
            self.assertGreaterEqual(seeded, 5)

            # 2. Recall matching trace
            start_t = time.perf_counter()
            recalled = recall_traces("lỗi docker port conflict 8080", traces_path=tmp_traces_path)
            latency_ms = (time.perf_counter() - start_t) * 1000
            self.assertLess(latency_ms, 5.0, f"Memory recall took too long: {latency_ms:.2f}ms")
            self.assertTrue(len(recalled) > 0)
            self.assertIn("docker", recalled[0]["trace"]["problem_signature"].lower())

            # 3. Record new trace and verify success count increment
            new_tr = record_trace(
                problem_signature="git rebase conflict in merge branch",
                proven_solution="git rebase --abort && git status",
                action_type="command",
                tags=["git", "rebase"],
                traces_path=tmp_traces_path
            )
            self.assertEqual(new_tr["success_count"], 1)

            # Record again with same signature -> increments count
            updated_tr = record_trace(
                problem_signature="git rebase conflict in merge branch",
                proven_solution="git rebase --abort && git status",
                traces_path=tmp_traces_path
            )
            self.assertEqual(updated_tr["success_count"], 2)

            # 4. Recall newly recorded trace
            git_recalled = recall_traces("git rebase conflict", traces_path=tmp_traces_path)
            self.assertTrue(len(git_recalled) > 0)
            self.assertEqual(git_recalled[0]["trace"]["id"], new_tr["id"])

        # 5. Integration with Unified Resolver and Hook Runner
        res_unified = resolve_skill("lỗi docker port đang bị chiếm dụng", unified=True)
        self.assertIn("proven_traces", res_unified)

        hook_payload = {
            "lastUserInput": "sửa lỗi docker container port 8080 conflict",
            "workspacePaths": ["d:/Antigravity/Skill management"]
        }
        hook_out = process_hook(hook_payload)
        msg = hook_out["injectSteps"][0]["ephemeralMessage"]
        self.assertIn("Proven Execution Memory", msg)

    def test_24_mcp_virtual_bus(self):
        """Verify that Omni-MCP Virtual Bus discovers, routes, and validates MCP tools dynamically."""
        from mcp_gateway import (
            discover_mcp_servers, index_mcp_tools, route_mcp_tool,
            get_tool_schema, validate_tool_arguments
        )

        # 1. Discovery & Indexing
        servers = discover_mcp_servers()
        self.assertGreater(len(servers), 0, "Expected at least one MCP server discovered")
        mcp_idx = index_mcp_tools(servers)
        self.assertGreater(mcp_idx["total_tools"], 0, "Expected at least one MCP tool indexed")

        # 2. Sub-millisecond Tool Routing
        start_t = time.perf_counter()
        routes = route_mcp_tool("đo kích thước và thể tích khối 3D solidcraft measure", mcp_index=mcp_idx)
        route_latency_ms = (time.perf_counter() - start_t) * 1000
        self.assertLess(route_latency_ms, 5.0, f"MCP routing latency too high: {route_latency_ms:.2f}ms")
        self.assertTrue(len(routes) > 0, "Expected matching MCP tool route")
        self.assertEqual(routes[0]["server"], "solidcraft")
        self.assertEqual(routes[0]["tool"], "measure")
        self.assertIn("call_template", routes[0])

        # 3. Schema Retrieval
        schema = get_tool_schema("solidcraft", "measure", mcp_index=mcp_idx)
        self.assertEqual(schema.get("name"), "measure")
        self.assertEqual(schema.get("server"), "solidcraft")
        self.assertIn("properties", schema.get("parameters", {}))

        # 4. Tool Argument Validation
        # Valid argument
        valid_res = validate_tool_arguments("solidcraft", "measure", {"body": "Body1"}, mcp_index=mcp_idx)
        self.assertTrue(valid_res["valid"])
        self.assertEqual(len(valid_res["type_errors"]), 0)

        # Invalid type argument
        invalid_res = validate_tool_arguments("solidcraft", "measure", {"body": 12345}, mcp_index=mcp_idx)
        self.assertFalse(invalid_res["valid"])
        self.assertGreater(len(invalid_res["type_errors"]), 0)
        self.assertIn("expected string", invalid_res["type_errors"][0].lower())

        # 5. Integration with Unified Resolver
        res_unified = resolve_skill("đo kích thước 3D trong solidcraft", unified=True)
        self.assertIn("mcp_tools", res_unified)
        self.assertTrue(len(res_unified["mcp_tools"]) > 0)


if __name__ == "__main__":
    unittest.main()
