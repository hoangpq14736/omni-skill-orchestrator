# 🧠 Omni-Kernel v4.1: Universal Autonomous Cognitive Operating System

[![Agent Plugins 1.0.0](https://img.shields.io/badge/Spec-Agent%20Plugins%201.0.0-blue.svg)](https://agent-plugins.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)
[![Zero Dependency Kernel](https://img.shields.io/badge/Dependencies-0%20(Pure%20Stdlib%20Kernel)-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-277%2F277%20Passing-success.svg)]()
[![Council Gate](https://img.shields.io/badge/DeepSeek%20Council%20Gate-APPROVED-brightgreen.svg)](docs/audits/omni_kernel_v41_final_approved_verdict.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) • [Tiếng Việt](README.vi.md)

> **Universal Autonomous AI Cognitive Kernel for Google Antigravity, Claude Code, Cursor, and Agentic Frameworks.**  
> *Equipped with Tri-Tier Omni-Memory v4.1 Hierarchy, Independent Architecture Gatekeeper Omni-Auditor (DeepSeek-V4.1-Flash), Heterogeneous Dual Worker Fleet (Groq Cloud LPU + Local MI50 GPU), Native GitHub Spec Kit (Spec-Driven Development), and JIT Cognitive Routing with zero static token bloat.*

---

## ⚡ Why Omni-Kernel?

Traditional AI agent configurations suffer from static context bloat, fragile hardcoded prompts, runaway token consumption, and an inability to adapt to unfamiliar technical stacks.

| Dimension | Traditional Agents & Static Skills | Omni-Kernel v4.1 |
|---|---|---|
| **Context Overhead** | Injects 50–120 skills & static rules into System Prompt (**15,000–25,000 tokens**), hitting context ceilings and degrading model IQ. | **< 300 Tokens at idle!** Ring 0 Invariants stay lean; domain rules, skills, and tools are resolved Just-In-Time (JIT). |
| **Long-Term Memory** | Flat JSON files or heavy vector DBs that corrupt easily or introduce unacceptable chat latency (>500ms). | **Tri-Tier Omni-Memory**: Tier 1 RAM Reflex (<0.3ms); Tier 2 Embedded SQLite WAL with Dual-Column FTS5 BM25 + CPU ONNX Embeddings (<15ms, 0MB VRAM); Tier 3 Consolidator with Ebbinghaus decay. |
| **Architectural Gatekeeping** | Internal subagents create an "Echo Chamber", blindly approving each other's hallucinations. | **Omni-Auditor Gatekeeper (DeepSeek-V4.1-Flash)**: Independent external Red-Teaming Devil's Advocate (1M context), strictly enforced via `hook_runner.py` without blocking hook turnaround. |
| **Code Execution Fleet** | Primary model wastes expensive tokens typing boilerplate, slowing down turnaround. | **Specialized Dual Worker Fleet**: Groq Cloud LPU (300-800+ tok/s for tests & boilerplate) paired with Local AMD Instinct MI50 GPU (100% offline, local fast edit, SQLite WAL). |
| **Engineering Rigor (SDD)** | Coding without formal specifications, causing architectural regressions and drift. | **Native GitHub Spec Kit Integration**: Standardized 10-phase lifecycle (Constitution, Specify, Clarify, Plan, Tasks, Implement, Converge...). |
| **Speed & Dependencies** | Relies on heavy external dependencies and fragile runtime wrappers. | **Pure Python Stdlib Core (0 External Dependencies for Kernel, Hook & FTS5)**. Indexes 500+ skills in **0.12s**, resolves warm in **~2–5ms** (**~1ms** without workspace, **~0.11s** CLI cold start). Optional CPU ONNX Runtime for Tier 2 Semantic Search with automatic fallback to SQLite FTS5 BM25. |

---

## 🏗️ System Architecture

Omni-Kernel v4.1 operates with a deterministic layered structure:

```text
                      ┌────────────────────────────────────────────────────────┐
                      │              COMMANDER: ANTIGRAVITY                    │
                      │             (Planning, UI, Orchestration)              │
                      └───────────────────────────┬────────────────────────────┘
                                                  │
                                                  ▼
                      ┌────────────────────────────────────────────────────────┐
                      │       HARD GATEKEEPER HOOK (hook_runner.py, <25ms)     │
                      │  - Tier 1: L1 Reflex RAM Cache (<0.3ms, 0 Token)       │
                      │  - Fast Detection of RFC/SDD/Major Diff (<1ms)         │
                      │  - Injects Mandatory Directive into Ephemeral Context  │
                      └───────────────────────────┬────────────────────────────┘
                                                  │ (Enforces Commander to Invoke)
                                                  ▼
                                  ┌────────────────────────────────┐
                                  │   DEEPSEEK-V4.1-FLASH AUDITOR  │
                                  │   (Strict Architecture Critic) │
                                  │   - 1M Tokens Context Window   │
                                  │   - Red-Teaming Persona        │
                                  │   - Zero Echo-Chamber          │
                                  └───────────────┬────────────────┘
                                                  │
                         ┌────────────────────────┴────────────────────────┐
                         ▼ (Approved)                                      ▼ (Rejected / Critique)
            ┌───────────────────────────┐                         ┌──────────────────┐
            │    DUAL WORKER FLEET      │                         │ Return Critique  │
            ├─────────────┬─────────────┤                         │ Require Planner  │
            │  Local MI50 │  Groq Cloud │                         │ Refinement       │
            │  (AMD 16GB) │  (LPU 120B) │                         └──────────────────┘
            │ SQLite WAL  │ Test Suite &│
            │ 100% Offline│ Boilerplate │
            └─────────────┴─────────────┘
```

> **⚡ Note on Hook Decoupling & SLA:** `hook_runner.py` in-process reflex logic (`process_hook()`) completes in **`<25ms`** (`~16ms` median; `~120ms` full Python CLI subprocess turnaround on Windows) because it **does NOT make synchronous network calls** to DeepSeek. Instead, it inspects disk artifact freshness, verifies cryptographic file hashes, and injects a non-bypassable directive (`[CRITICAL ARCHITECTURE GATEKEEPER DIRECTIVE]`) forcing the Commander agent to invoke the `deepseek_worker_cloud` MCP tool.

---

## 🧠 Tri-Tier Omni-Memory v4.1 Architecture

All verified solutions, execution traces, and episodic experiences are governed through three tiers:

1. **Tier 1 (L1 Ephemeral Reflex - <0.3ms cache reflex, <25ms in-process hook logic / ~120ms subprocess)**:
   - PreInvocation hook written in 100% Python Standard Library in `scripts/hook_runner.py`.
   - Reads lightning-fast RAM cache from `scripts/proven_traces.json` in <0.02ms.
   - Logs events asynchronously into `l1_staging_spool.jsonl` / `l1_staging_log` without blocking user interaction.

2. **Tier 2 (L2 Hybrid Episodic Memory - <15ms retrieval, 0MB VRAM Tax)**:
   - Embedded SQLite database at `omni_memory.db` operating in **WAL mode** (`PRAGMA synchronous = NORMAL;`, `busy_timeout = 5000;`).
   - Hybrid search combining **Dual-Column FTS5 BM25** (`content_exact` weight 10.0 vs `content_folded` weight 1.0) with **CPU ONNX Embeddings** (`paraphrase-multilingual-MiniLM-L12-v2`, INT8 quantization, 0MB VRAM, ~7ms) via Reciprocal Rank Fusion ($k=20$).
   - *Graceful Degradation:* If ONNX runtime is absent, Tier 2 automatically falls back to 100% pure-stdlib Dual-Column SQLite FTS5 BM25 without throwing exceptions.

3. **Tier 3 (L3 Background Consolidator Daemon)**:
   - Out-of-band daemon `scripts/consolidator.py` consumes pending staging records.
   - Auto-promotes multi-hit patterns ($\ge 2$ successes) with automated bilingual tags.
   - Applies Ebbinghaus stability decay, soft-archives stale records, and uses `PRAGMA wal_checkpoint(PASSIVE)` to completely prevent lock contention on Windows NTFS.

---

## 🛠️ Core Module Registry

| Component | Path | Description |
|---|---|---|
| **Omni-Auditor Gatekeeper** | `scripts/consult_critic.py` | 100% stdlib REST client connecting to DeepSeek-V4.1-Flash API for architecture critique (1M context, 30s timeout, jittered backoff). |
| **Auditor MCP Server** | `mcp/deepseek_worker_mcp.py` | JSON-RPC 2.0 stdio server providing `deepseek_audit_spec` and `deepseek_audit_diff` tools. |
| **Tri-Tier Memory Engine** | `scripts/memory_engine.py` | Hybrid memory search engine combining FTS5 BM25 + ONNX Dense Vector Embeddings with RRF ranking. |
| **Memory Consolidator** | `scripts/consolidator.py` | Daemon consuming staging logs, promoting multi-hit knowledge, decaying stability, and compacting SQLite via passive checkpoints. |
| **PreInvocation Hook** | `scripts/hook_runner.py` | Deterministic hard gatekeeper & JIT L1 Reflex injector (<25ms in-process logic, ~120ms subprocess). |
| **Spec-Driven Development** | `skills/spec-driven-development/` | Native GitHub Spec Kit SDD engine implementing the 10-phase lifecycle (Constitution, Spec, Plan, Tasks, Implement...). |
| **Dual-Tier Router** | `scripts/dual_tier.py` | Computes task complexity (0-100), applies Quota Guard to simple tasks, and delegates to L2 Strategist. |
| **Weekly Reporter** | `scripts/reporter.py` | Generates executive reports detailing operational KPIs, token savings, top skills, and system health. |
| **Workspace Assimilator** | `scripts/assimilator.py` | Non-destructively scans and ingests `.cursorrules`, `GEMINI.md`, `CLAUDE.md`, and `.specify/` rules. |
| **Kernel Synchronizer** | `scripts/kernel_sync.py` | Detects and auto-heals Version Drift across Workspace, Plugins, and Library skills. |

---

## 🧪 Comprehensive Automated Testing & Council Gate Verification

Omni-Kernel v4.1 maintains an exhaustive automated test suite with **100% pass rate (277/277 Tests PASS, 0 Skipped: 117/117 in full pytest suite + 160/160 in remediation verification suites)** and an official cryptographically signed **`APPROVED`** verdict from the DeepSeek-V4.1-Flash Council Gate ([`docs/audits/omni_kernel_v41_final_approved_verdict.md`](docs/audits/omni_kernel_v41_final_approved_verdict.md), portable across `git clone` via SHA-256 content hash + HMAC-SHA256 verification):

```bash
# 1. Core Engine, Tri-Tier Memory & Auditor Spec Suites (117/117 passed in full tests/ + specs/; 110/110 passed for the 3 core paths)
python -m pytest tests/ specs/001-omni-memory-v4/tests/ specs/002-deepseek-v41-auditor/tests/

# 2. Cluster 1–3 & Round 7–9 Remediation Verification Suites (160 tests)
python scripts/test_cluster_1_remediation.py   # 69/69 passed (SQLite WAL, Outbox 2PC, SHA-256 Partitioning)
python scripts/test_cluster_2_remediation.py   # 51/51 passed (Hook <25ms SLA, HMAC Gate, Trust Lock, Lifecycle Epoch)
python scripts/test_cluster_3_remediation.py   # 17/17 passed (Resolver, AST Sandbox, CoW Stale-While-Revalidate)
python scripts/test_round_7_remediation.py     # 23/23 passed (Cross-Cluster Integration, Proven Recall & Edge Cases)
```

---

## 🤝 Engineering Philosophy: Built on Ponytail

Omni-Kernel v4.1 strictly adheres to the **Ponytail Engineering Philosophy**:
* **The best code is the code never written.** The smallest complete working diff wins.
* **Pure Python Standard Library for Kernel Core**: Kernel, Gatekeeper Hook, and SQLite FTS5 search have **zero external dependencies** (`os`, `sqlite3`, `urllib`, `re`, `json`). Optional ONNX Runtime is isolated to Tier 2 semantic vector search.
* Immutability first, fail loudly with diagnostic context, and never silently swallow exceptions.
* JIT ephemeral context injection over permanent static prompt bloat.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
