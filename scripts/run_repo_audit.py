#!/usr/bin/env python3
"""
Omni-Kernel v4.1: Repository-Wide Architectural Red-Teaming Audit Runner
Powered by DeepSeek-Flash (thinking=high).
Audits the entire codebase across 5 distinct architectural clusters.
Generates structured markdown reports and an executive master summary.
"""

import os
import sys
import time
import json
import hashlib
from typing import Dict, List, Any

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import consult_critic
from consult_critic import redact_credentials

CLUSTERS = [
    {
        "id": "cluster_1_memory_concurrency",
        "name": "Cluster 1: Memory Engine, Concurrency & SQLite WAL",
        "mode": "code",
        "files": [
            "scripts/memory_engine.py",
            "scripts/memory_schema.py",
            "scripts/consolidator.py",
            "scripts/test_wal_concurrency.py"
        ],
        "focus": "SQLite WAL concurrency, lock collisions, multi-threading race conditions, Ebbinghaus decay math, FTS5 safety."
    },
    {
        "id": "cluster_2_preflight_hook_latency",
        "name": "Cluster 2: Pre-Flight Hook, Latency & IPI Sanitizer",
        "mode": "code",
        "files": [
            "scripts/hook_runner.py",
            "scripts/dual_tier.py",
            "scripts/workspace_sanitizer.py",
            "scripts/lifecycle_guard.py",
            "scripts/kernel_sync.py"
        ],
        "focus": "SLA <25ms, TOCTOU safety, Indirect Prompt Injection (IPI) prevention, bounded LRU caching, Windows NTFS atomic writes."
    },
    {
        "id": "cluster_3_resolver_arbitration_bus",
        "name": "Cluster 3: Resolver, Arbitration, Dynamic Bus & Indexer",
        "mode": "code",
        "files": [
            "scripts/resolver.py",
            "scripts/indexer.py",
            "scripts/mcp_gateway.py",
            "scripts/synthesizer.py",
            "scripts/assimilator.py"
        ],
        "focus": "Inverted index RAM footprint, ReDoS vulnerability, skill arbitration tie-breakers, dynamic MCP dispatch."
    },
    {
        "id": "cluster_4_specs_sdd_blueprints",
        "name": "Cluster 4: Specifications & SDD Blueprints",
        "mode": "rfc",
        "files": [
            ".specify/constitution.md",
            "specs/001-omni-memory-v4/spec.md",
            "specs/002-deepseek-v41-auditor/spec.md"
        ],
        "focus": "Architectural integrity, constitutional invariants (Principles I-V), boundary enforcement, schema consistency."
    },
    {
        "id": "cluster_5_contracts_tests_invariants",
        "name": "Cluster 5: Core Contracts, Testing & System Invariants",
        "mode": "code",
        "files": [
            "GEMINI.md",
            "rules/AGENTS.md",
            ".cursorrules",
            "plugin.json",
            "scripts/consult_critic.py",
            "scripts/test_dual_tier.py"
        ],
        "focus": "Ring 0 invariants permanence, mock testing fidelity, error handling (fail loudly), worker fleet delegation mandate."
    }
]


def bundle_cluster_files(cluster: Dict[str, Any]) -> str:
    """Reads and bundles files for a cluster into a clean markdown document."""
    parts = [
        f"# ARCHITECTURAL AUDIT TARGET: {cluster['name']}\n",
        f"**Audit Focus**: {cluster['focus']}\n\n",
        "## TARGET SOURCE FILES BUNDLE\n"
    ]
    MAX_BUNDLE_FILE_SIZE = 512 * 1024  # 512 KiB cap per file (VULN-002)
    for rel_path in cluster["files"]:
        full_path = os.path.join(_REPO_ROOT, rel_path)
        if not os.path.exists(full_path):
            continue
        try:
            if os.path.getsize(full_path) > MAX_BUNDLE_FILE_SIZE:
                parts.append(f"### File: `{rel_path}` (Skipped: exceeds 512 KiB size limit)\n")
                continue
            with open(full_path, "r", encoding="utf-8", errors="ignore") as fp:
                content = fp.read(MAX_BUNDLE_FILE_SIZE)
            parts.append(f"### File: `{rel_path}`\n```python\n{content}\n```\n")
        except Exception as e:
            parts.append(f"### File: `{rel_path}` (Error reading: {e})\n")
    return "\n".join(parts)


def run_all_audits():
    out_dir = os.path.join(_REPO_ROOT, "docs", "audits")
    os.makedirs(out_dir, exist_ok=True)

    api_key = consult_critic.load_api_key()
    api_base = os.environ.get("DEEPSEEK_API_BASE", consult_critic.DEFAULT_API_BASE)
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")

    print("=" * 70)
    print("🛡️ OMNI-KERNEL v4.1: REPO-WIDE ARCHITECTURAL AUDIT RUNNER")
    print(f"🤖 Model: {model} (reasoning=high, thinking=enabled)")
    print(f"📂 Target Clusters: {len(CLUSTERS)}")
    print("=" * 70)

    t_start = time.time()
    results = []

    for idx, cluster in enumerate(CLUSTERS, 1):
        print(f"\n[{idx}/{len(CLUSTERS)}] Auditing {cluster['name']}...")
        bundle_text = bundle_cluster_files(cluster)
        sanitized = redact_credentials(bundle_text)
        input_hash = f"sha256:{hashlib.sha256(sanitized.encode('utf-8')).hexdigest()}"
        system_prompt = consult_critic.build_system_prompt(cluster["mode"])

        t0 = time.time()
        try:
            verdict_data, final_model = consult_critic.execute_critic_request(
                api_key=api_key,
                api_base=api_base,
                model=model,
                system_prompt=system_prompt,
                user_content=sanitized,
                temperature=0.2,
                timeout_budget=180.0
            )
            elapsed = time.time() - t0
            verdict = verdict_data.get("verdict", "REJECTED")
            confidence = verdict_data.get("confidence_score", 0.0)
            vulns_count = len(verdict_data.get("critical_vulnerabilities", []))
            concurrency_count = len(verdict_data.get("concurrency_hazards", []))

            print(f"  -> Verdict: {verdict} (Confidence: {confidence:.2f}) | {elapsed:.1f}s")
            print(f"  -> Findings: {vulns_count} vulnerabilities, {concurrency_count} concurrency hazards")

            markdown_report = consult_critic.format_markdown_report(
                data=verdict_data,
                target_file=cluster["name"],
                input_hash=input_hash,
                model=final_model
            )

            report_file = os.path.join(out_dir, f"{cluster['id']}.md")
            with open(report_file, "w", encoding="utf-8") as rf:
                rf.write(markdown_report)

            json_file = os.path.join(out_dir, f"{cluster['id']}.json")
            with open(json_file, "w", encoding="utf-8") as jf:
                json.dump(verdict_data, jf, indent=2, ensure_ascii=False)

            results.append({
                "cluster": cluster,
                "verdict": verdict,
                "confidence": confidence,
                "vulns_count": vulns_count,
                "concurrency_count": concurrency_count,
                "elapsed": elapsed,
                "report_file": report_file,
                "data": verdict_data
            })

        except Exception as e:
            print(f"  [!] LỖI AUDIT: {e}")
            results.append({
                "cluster": cluster,
                "verdict": "ERROR",
                "confidence": 0.0,
                "vulns_count": 0,
                "concurrency_count": 0,
                "elapsed": 0.0,
                "error": str(e)
            })

    total_time = time.time() - t_start

    # Build Master Summary Report
    master_lines = [
        "# 🛡️ Omni-Kernel v4.1: Repository Master Architectural Audit",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')} UTC | **Auditor Model:** `{model}` | **Total Elapsed:** {total_time:.1f}s\n",
        "## Executive Summary Table",
        "| Cluster | Verdict | Confidence | Vulnerabilities | Concurrency Hazards | Report Artifact |",
        "| :--- | :---: | :---: | :---: | :---: | :--- |"
    ]

    total_vulns = 0
    total_hazards = 0
    for r in results:
        c_name = r["cluster"]["name"]
        verdict = r["verdict"]
        conf = f"{r.get('confidence', 0.0):.2f}"
        v_cnt = r.get("vulns_count", 0)
        h_cnt = r.get("concurrency_count", 0)
        total_vulns += v_cnt
        total_hazards += h_cnt
        r_link = f"[{os.path.basename(r.get('report_file', ''))}](./{os.path.basename(r.get('report_file', ''))})"
        master_lines.append(f"| **{c_name}** | `{verdict}` | {conf} | {v_cnt} | {h_cnt} | {r_link} |")

    master_lines.append(f"\n**Total Vulnerabilities Identified:** {total_vulns} | **Total Concurrency Hazards:** {total_hazards}\n")

    master_lines.append("## Consolidated Actionable Remediation Plan")
    for r in results:
        if r["verdict"] != "ERROR":
            master_lines.append(f"\n### {r['cluster']['name']}")
            directives = r["data"].get("prescriptive_directives", [])
            for d in directives:
                master_lines.append(f"- [ ] {d}")

    master_file = os.path.join(out_dir, "MASTER_AUDIT_REPORT.md")
    with open(master_file, "w", encoding="utf-8") as mf:
        mf.write("\n".join(master_lines))

    print("\n" + "=" * 70)
    print(f"🎉 MASTER AUDIT COMPLETED in {total_time:.1f}s!")
    print(f"📄 Master Report: {master_file}")
    print(f"📊 Total Vulnerabilities: {total_vulns} | Total Hazards: {total_hazards}")
    print("=" * 70)


if __name__ == "__main__":
    run_all_audits()
