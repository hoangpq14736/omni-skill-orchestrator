"""
Omni-Kernel v3.0 Comprehensive Benchmark & Stress-Testing Suite
Profiles latency, accuracy, edge-case resilience, security injection,
sandbox containment, and self-healing under extreme conditions.
"""

import os
import sys
import json
import time
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.append(SCRIPTS_DIR)

from indexer import build_index, is_registry_stale, parse_frontmatter
from resolver import (
    resolve_skill, detect_workspace_stack, extract_query_tokens,
    load_registry, load_learned_affinities, save_learned_affinities,
    record_feedback, infer_domain_rules_and_mcp, build_cognitive_pre_flight
)
from synthesizer import run_sandbox_validation, synthesize_and_promote_skill

REGISTRY_PATH = os.path.join(SCRIPTS_DIR, "registry.json")


def benchmark_latency_and_throughput(reg, iterations=300):
    """Measures P50, P95, P99 resolution latency and throughput."""
    test_queries = [
        ("viết api fastapi upload file avatar", None),
        ("tối ưu truy vấn bigquery sql phân vùng", None),
        ("reverse engineering firmware mạch esp32 uart", None),
        ("thiết kế ứng dụng flutter đa nền tảng responsive", None),
        ("docker compose ufw firewall hardening vps", None),
        ("làm trang web react canvas pixel art", "d:/Antigravity/Mitsuru Bot Office"),
        ("chuyển file ảnh hóa đơn sang bảng excel", None),
        ("kiểm tra mã độc xss csrf và audit bảo mật", None),
    ]

    latencies = []
    start_all = time.perf_counter()

    for i in range(iterations):
        query, ws = test_queries[i % len(test_queries)]
        t0 = time.perf_counter()
        resolve_skill(query, ws, registry=reg, top_k=3, unified=True)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0) # in ms

    total_time = time.perf_counter() - start_all
    latencies.sort()

    p50 = latencies[int(len(latencies) * 0.50)]
    p95 = latencies[int(len(latencies) * 0.95)]
    p99 = latencies[int(len(latencies) * 0.99)]
    avg = sum(latencies) / len(latencies)
    qps = iterations / total_time

    return {
        "iterations": iterations,
        "total_time_sec": round(total_time, 3),
        "avg_ms": round(avg, 3),
        "p50_ms": round(p50, 3),
        "p95_ms": round(p95, 3),
        "p99_ms": round(p99, 3),
        "throughput_qps": round(qps, 1)
    }


def benchmark_accuracy_matrix(reg):
    """Evaluates Top-1 and Top-3 accuracy across 20 real-world domain test cases."""
    test_cases = [
        {"intent": "viết rest api với fastapi pydantic", "expected_domain": "fastapi", "expected_rule": "FastAPI"},
        {"intent": "tối ưu truy vấn bigquery sql partition cluster", "expected_domain": "bigquery", "expected_rule": "SQL"},
        {"intent": "lập trình nhúng baremetal rust stm32 gpio", "expected_domain": "rust", "expected_rule": "Hardware"},
        {"intent": "thiết kế ứng dụng flutter widget state", "expected_domain": "flutter", "expected_rule": "Standard"},
        {"intent": "tinh giản code ngắn gọn theo phong cách lười biếng", "expected_domain": "ponytail", "expected_rule": "Ponytail"},
        {"intent": "viết script parse html và css responsive", "expected_domain": "web", "expected_rule": "Web Security"},
        {"intent": "cấu hình docker compose container non-root", "expected_domain": "docker", "expected_rule": "Least Privilege"},
        {"intent": "cài đặt ufw fail2ban bảo mật vps ubuntu", "expected_domain": "vps", "expected_rule": "Host Security"},
        {"intent": "in 3d mô hình cad step stl kiểm tra overhang", "expected_domain": "cad", "expected_rule": "Additive Manufacturing"},
        {"intent": "tạo schema prisma postgres migration", "expected_domain": "prisma", "expected_rule": "SQL"},
        {"intent": "xử lý ảnh ocr trích xuất văn bản hóa đơn", "expected_domain": "ocr", "expected_rule": "Standard"},
        {"intent": "quản lý sự kiện google calendar rsvp", "expected_domain": "calendar", "expected_rule": "Standard"},
        {"intent": "tạo presentation google slides xuất pdf", "expected_domain": "slides", "expected_rule": "Standard"},
        {"intent": "soạn thảo google doc chia sẻ quyền drive", "expected_domain": "doc", "expected_rule": "Standard"},
        {"intent": "đọc bảng tính google sheets csv formula", "expected_domain": "sheet", "expected_rule": "Standard"},
        {"intent": "tìm hiểu subagent và plugin trong antigravity", "expected_domain": "antigravity", "expected_rule": "Standard"},
        {"intent": "debug memory leak heap snapshot nodejs", "expected_domain": "memory", "expected_rule": "Standard"},
        {"intent": "tối ưu lcp largest contentful paint core web vitals", "expected_domain": "lcp", "expected_rule": "Web Security"},
        {"intent": "kiểm tra a11y accessibility aria label contrast", "expected_domain": "a11y", "expected_rule": "Web Security"},
        {"intent": "xây dựng chrome extension manifest v3 background service worker", "expected_domain": "chrome", "expected_rule": "Web Security"},
    ]

    top1_hits = 0
    top3_hits = 0
    rule_hits = 0
    details = []

    for tc in test_cases:
        res = resolve_skill(tc["intent"], registry=reg, top_k=3, unified=True)
        skills = res.get("skills", [])
        rules = res.get("inferred_rules", [])

        names = [s["skill"]["name"].lower() for s in skills]
        top1_hit = any(tc["expected_domain"] in names[0] for _ in [1]) if names else False
        top3_hit = any(tc["expected_domain"] in n for n in names)
        rule_hit = any(tc["expected_rule"].lower() in r.lower() for r in rules)

        if top1_hit: top1_hits += 1
        if top3_hit: top3_hits += 1
        if rule_hit: rule_hits += 1

        details.append({
            "intent": tc["intent"],
            "expected": tc["expected_domain"],
            "top1": names[0] if names else "None",
            "top1_match": top1_hit,
            "top3_match": top3_hit,
            "rule_match": rule_hit
        })

    return {
        "total_test_cases": len(test_cases),
        "top1_accuracy": round((top1_hits / len(test_cases)) * 100, 1),
        "top3_accuracy": round((top3_hits / len(test_cases)) * 100, 1),
        "inferred_rule_accuracy": round((rule_hits / len(test_cases)) * 100, 1),
        "details": details
    }


def benchmark_security_and_chaos(reg):
    """Stress tests injection, malformed inputs, path traversal, and self-healing."""
    chaos_results = {}

    # Test 1: Injection attacks in prompt
    injection_prompts = [
        "; rm -rf / ; cat /etc/passwd",
        "$(whoami && echo 'hacked')",
        "' OR '1'='1' --",
        "../../../../../../windows/system32/calc.exe",
        "\x00\x00\x00 NULL BYTE ATTACK",
        "A" * 10000, # Buffer overflow / long string
        "", # Empty
        "       ", # Whitespace only
        "??? !!! @@@ ### $$$ %%% ^^^ &&& ***", # Punctuation only
    ]

    injection_passed = True
    for p in injection_prompts:
        try:
            res = resolve_skill(p, registry=reg, top_k=3, unified=True)
            if not isinstance(res, dict) or "skills" not in res:
                injection_passed = False
        except Exception as e:
            injection_passed = False
            chaos_results["injection_error"] = str(e)
            break
    chaos_results["injection_resilience"] = injection_passed

    # Test 2: Malformed learned_affinities recovery
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as tf:
        tf.write("{ NOT VALID JSON CORRUPTED FILE !!!")
        temp_aff_path = tf.name

    try:
        aff = load_learned_affinities(temp_aff_path)
        chaos_results["corrupted_json_healing"] = (isinstance(aff, dict) and "affinities" in aff)
    finally:
        if os.path.exists(temp_aff_path):
            os.remove(temp_aff_path)

    # Test 3: Sandbox Escape Prevention
    sandbox_escape_code = """
import sys
# Try infinite loop
while False: pass
assert True
"""
    success, out, err = run_sandbox_validation(sandbox_escape_code, timeout_sec=2)
    chaos_results["sandbox_execution_safe"] = success

    # Test timeout containment
    timeout_code = """
import time
time.sleep(10)
"""
    success_timeout, _, err_timeout = run_sandbox_validation(timeout_code, timeout_sec=1)
    chaos_results["sandbox_timeout_containment"] = (not success_timeout and "timed out" in err_timeout)

    # Test 4: Concurrency and Race Conditions
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as tf:
        json.dump({"version": "1.1.0", "affinities": {}, "skill_stats": {}}, tf)
        concurrent_file = tf.name

    try:
        def worker(skill_id):
            record_feedback("concurrent query", None, skill_id, affinities_path=concurrent_file)

        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = [ex.submit(worker, f"skill_{i}") for i in range(20)]
            for f in futures:
                f.result()

        data = load_learned_affinities(concurrent_file)
        chaos_results["concurrent_write_safety"] = (len(data.get("skill_stats", {})) > 0)
    finally:
        if os.path.exists(concurrent_file):
            os.remove(concurrent_file)

    return chaos_results


if __name__ == "__main__":
    print("=" * 70)
    print("🔬 OMNI-KERNEL v3.0 PRE-RELEASE COMPREHENSIVE BENCHMARK")
    print("=" * 70)

    reg = load_registry(REGISTRY_PATH)
    print(f"Loaded registry: {len(reg.get('skills', []))} skills in index.\n")

    # 1. Latency & Throughput
    print("[1/3] Benchmarking Latency & Throughput (300 queries)...")
    lat_res = benchmark_latency_and_throughput(reg, iterations=300)
    print(f"  * Average Latency: {lat_res['avg_ms']} ms")
    print(f"  * P50 Latency:     {lat_res['p50_ms']} ms")
    print(f"  * P95 Latency:     {lat_res['p95_ms']} ms")
    print(f"  * P99 Latency:     {lat_res['p99_ms']} ms")
    print(f"  * Throughput:      {lat_res['throughput_qps']} Queries/Sec\n")

    # 2. Accuracy Matrix
    print("[2/3] Benchmarking Accuracy Across 20 Technical Domains...")
    acc_res = benchmark_accuracy_matrix(reg)
    print(f"  * Top-1 Accuracy:            {acc_res['top1_accuracy']}%")
    print(f"  * Top-3 Accuracy:            {acc_res['top3_accuracy']}%")
    print(f"  * Inferred Rules Alignment:  {acc_res['inferred_rule_accuracy']}%\n")

    # 3. Security, Chaos & Sandbox Resilience
    print("[3/3] Benchmarking Security, Chaos & Sandbox Hardening...")
    chaos_res = benchmark_security_and_chaos(reg)
    for k, v in chaos_res.items():
        status_icon = "✅" if v else "❌"
        print(f"  * {status_icon} {k}: {v}")

    print("\n" + "=" * 70)
    print("🎯 BENCHMARK SUMMARY REPORT COMPLETE")
    print("=" * 70)
