#!/usr/bin/env python3
"""
Unit Test Suite for Omni-Kernel v4.1 Dual-Tier Complexity Router
Asserts:
1. Length Fallacy defeat (Short Paxos/Memory leak vs Long Cosmetic CSS)
2. Symptom Trap defeat (Double charge, random crash)
3. Acceptable Waste & Negation safety
4. Workspace Vitals baseline elevation
5. Sub-0.1ms latency benchmark
"""

import os
import sys
import tempfile
import time

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from dual_tier import ComplexityRouter, calculate_task_complexity


def test_length_fallacy_defeat():
    # 15-char architectural command must elevate to Tier 2
    res_paxos = calculate_task_complexity("Implement Paxos")
    assert res_paxos["score"] == 100, f"Expected 100 for Paxos, got {res_paxos['score']}"
    assert res_paxos["tier"] == 2
    assert res_paxos["recommend_subagent"] is True

    # 15-char memory leak command must elevate to Tier 2
    res_mem = calculate_task_complexity("Fix memory leak")
    assert res_mem["score"] == 100
    assert res_mem["tier"] == 2

    # Verbose 150-char cosmetic command must remain Tier 1 (L1 Reflex)
    cosmetic_prompt = (
        "Đổi màu nút Submit thành màu xanh navy #001f3f, chỉnh padding top 12px, "
        "margin 8px, căn giữa text, bo tròn border 6px, thêm shadow mờ và đổi font chữ sang Roboto"
    )
    res_cosmetic = calculate_task_complexity(cosmetic_prompt)
    assert res_cosmetic["score"] < 50, f"Expected cosmetic < 50, got {res_cosmetic['score']}"
    assert res_cosmetic["tier"] == 1
    assert res_cosmetic["recommend_subagent"] is False


def test_symptom_trap_defeat():
    # Symptom without academic keywords (e.g., race condition) must trigger Tier 2
    prompt_symptom = "Tài khoản bị trừ tiền 2 lần khi user bấm click đúp liên tục"
    res = calculate_task_complexity(prompt_symptom)
    assert res["score"] >= 50, f"Expected symptom >= 50, got {res['score']}"
    assert res["tier"] == 2
    assert any("Critical Failure Symptom" in f for f in res["factors"])

    # Flaky / random crash symptom
    prompt_flaky = "App thỉnh thoảng chết ngẫu nhiên khi nhiều user cùng lưu dữ liệu"
    res_flaky = calculate_task_complexity(prompt_flaky)
    assert res_flaky["score"] >= 50
    assert res_flaky["tier"] == 2


def test_acceptable_waste_negation():
    # Negation referencing concurrency in cosmetic prompt safely triggers Tier 2
    prompt = "Chỉ sửa lại đoạn text thông báo, đừng đụng vào logic concurrency nhé"
    res = calculate_task_complexity(prompt)
    assert res["tier"] == 2, "Acceptable Waste: High-risk term triggers Tier 2 to prevent DB destruction"


def test_workspace_vitals_elevation():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock Cargo.toml in the temporary workspace
        cargo_path = os.path.join(tmpdir, "Cargo.toml")
        with open(cargo_path, "w", encoding="utf-8") as f:
            f.write('[package]\nname = "distributed-node"\nversion = "0.1.0"\n')

        # Vague task inside a Rust workspace gets boosted baseline
        res = calculate_task_complexity("Sửa lỗi tính toán trong module helper", workspace_dir=tmpdir)
        assert res["score"] >= 25, f"Expected workspace boost >= 25, got {res['score']}"
        assert any("Cargo.toml" in f for f in res["factors"])


def test_latency_benchmark():
    prompts = [
        "Implement Paxos",
        "Đổi màu nút Submit thành màu đỏ",
        "Tài khoản bị trừ tiền 2 lần khi user bấm click đúp liên tục",
        "Viết lại hệ thống Auth dùng JWT và Redis cache",
        "Fix bug syntax error dòng 15",
    ]
    t0 = time.perf_counter()
    iterations = 2000
    for _ in range(iterations):
        for p in prompts:
            calculate_task_complexity(p)
    t1 = time.perf_counter()
    total_calls = iterations * len(prompts)
    avg_latency_ms = ((t1 - t0) * 1000) / total_calls
    print(f"✅ Verified {total_calls} calls: {avg_latency_ms * 1000:.2f} µs per call ({avg_latency_ms:.4f} ms)")
    assert avg_latency_ms < 0.1, f"Latency {avg_latency_ms} ms exceeds 0.1ms budget!"


def main():
    print("🧪 Running Omni-Kernel Dual-Tier Complexity Router Test Suite...")
    test_length_fallacy_defeat()
    print("  ✓ Length Fallacy Defeated")
    test_symptom_trap_defeat()
    print("  ✓ Symptom Trap Defeated")
    test_acceptable_waste_negation()
    print("  ✓ Acceptable Waste & Negation Invariant Verified")
    test_workspace_vitals_elevation()
    print("  ✓ Workspace Vitals Baseline Verified")
    test_latency_benchmark()
    print("  ✓ Latency Benchmark (<0.1ms) Passed")
    print("\n🎉 ALL TESTS PASSED!")


if __name__ == "__main__":
    main()
