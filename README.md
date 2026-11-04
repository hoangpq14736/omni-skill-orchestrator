# 🧠 Omni-Skill Orchestrator v4.1: Adaptive JIT Harness & Reflex Memory for AI Agents

[![Agent Plugins 1.0.0](https://img.shields.io/badge/Spec-Agent%20Plugins%201.0.0-blue.svg)](https://agent-plugins.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)
[![Zero Dependency Kernel](https://img.shields.io/badge/Dependencies-0%20(Pure%20Stdlib%20Core)-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-277%2F277%20Passing-success.svg)]()
[![Council Gate](https://img.shields.io/badge/DeepSeek%20Council%20Gate-APPROVED-brightgreen.svg)](docs/audits/omni_kernel_v41_final_approved_verdict.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) • [Tiếng Việt](README.vi.md)

> **A lightweight, local-first orchestration harness for Google Antigravity, Claude Code, Cursor, and AI coding agents.**  
> *Equipped with sub-millisecond JIT skill routing, Tri-Tier episodic memory (SQLite WAL + Dual-Column FTS5 BM25 + 384-dim CPU ONNX embeddings), autonomous skill synthesis, and decoupled architecture gatekeeping — with zero static prompt token bloat.*

---

## 🎯 What is Omni-Skill Orchestrator?

Omni is **not** a standalone autonomous coding agent (like Aider, OpenCode, or OpenHands). Instead, it is an **intelligent pre-flight harness and reflex layer** that sits in front of your primary agent (e.g., Antigravity, Claude Code):

1. **Stops System Prompt Bloat**: Rather than injecting 50–120 static skills and rules (costing 15,000–25,000 tokens per chat turn), Omni indexes 500+ skills in **0.12s** and injects only the top 1–3 relevant skills and rules **Just-In-Time (< 300 tokens)**.
2. **Cross-Session Reflex Memory**: Automatically captures successful fixes, indexes them into SQLite WAL with FTS5 BM25 and 384-dim CPU ONNX dense vectors (`intfloat/multilingual-e5-small`), and recalls matching proven solutions in **< 0.3ms**.
3. **Autonomous Skill Synthesis**: When encountering novel technical domains, Omni authors candidate `SKILL.md` documents, runs static AST security analysis, validates them in an isolated sandbox, and atomically promotes them into the local library.
4. **Decoupled Architecture Gatekeeper**: Inspects architecture intents (RFC, SDD, major diffs) in `< 25ms` in-process logic (`~120ms` full subprocess turnaround on Windows) without blocking the chat loop with synchronous cloud calls.

---

## ⚡ Feature Comparison

| Capability | Static Skills & Prompt Bloat | Omni-Skill Orchestrator v4.1 |
|---|---|---|
| **Context Overhead** | Injects 50–120 static skills (**15,000–25,000 tokens**), degrading model IQ and hitting context limits. | **< 300 Tokens at idle!** Invariants stay lean; domain skills, rules, and tools are resolved Just-In-Time (JIT). |
| **Routing Accuracy** | Naive substring matching often misroutes to irrelevant skills. | **Segment-Aware Scoring + Word Boundaries**: Differentiates domain subjects (`docker`, `sqlite`, `postgres`) from generic actions (`fix`, `debug`, `guide`). Achieves **100% Top-1 & Top-3 accuracy** on the 25-query Golden Benchmark. |
| **Episodic Memory** | Flat JSON files that corrupt or slow down chat, or heavy SaaS vector DBs. | **Tri-Tier Omni-Memory**: Tier 1 non-blocking RAM spool (<0.3ms); Tier 2 Embedded SQLite WAL with Dual-Column FTS5 BM25 + 384-dim CPU ONNX Embeddings (0MB VRAM tax); Tier 3 Consolidator with Ebbinghaus decay. |
| **Skill Synthesis** | Manual authoring required for every new library or tool. | **Autonomous Pipeline**: `scripts/synthesizer.py` authors templates, runs AST syntax checks, validates assertions in sandbox, and auto-indexes in <150ms. |
| **Architectural Gatekeeping** | Internal subagents create an "Echo Chamber", blindly approving each other's hallucinations. | **Decoupled Council Gate (DeepSeek-V4.1-Flash)**: Verified via HMAC-SHA256 signatures and SHA-256 target hashes without blocking hook turnaround. |
| **Core Dependencies** | Relies on heavy frameworks and unstable cloud services. | **Pure Python Standard Library Core** for Kernel, Hook, and SQLite FTS5 search (0 external dependencies). Optional `fastembed` for CPU vector search with automatic fallback to FTS5 BM25. |

---

## 🏗️ Layered Architecture

Omni operates as an interceptor harness around your AI agent:

```text
                      ┌────────────────────────────────────────────────────────┐
                      │              AI AGENT: ANTIGRAVITY / CLAUDE            │
                      │             (Planning, UI, Coding, Execution)          │
                      └───────────────────────────┬────────────────────────────┘
                                                  │ (Before every chat turn)
                                                  ▼
                      ┌────────────────────────────────────────────────────────┐
                      │     PRE-FLIGHT HARNESS HOOK (hook_runner.py, <25ms)    │
                      │  - L1 Reflex: Non-blocking append to spool (<0.3ms)    │
                      │  - JIT Skill Router: Segment-aware scoring (~2-5ms)    │
                      │  - Proven Trace Recall: High-precision memory (<0.3ms) │
                      │  - Gatekeeper: HMAC-SHA256 audit artifact verification │
                      └───────────────────────────┬────────────────────────────┘
                                                  │ (Injects <300 tokens JIT context)
                                                  ▼
                                      ┌───────────────────────┐
                                      │  INFORMED AGENT TURN  │
                                      └───────────────────────┘
```

---

## 🧠 Tri-Tier Omni-Memory Architecture

All verified solutions, execution traces, and episodic experiences are governed through three tiers:

1. **Tier 1 (L1 Ephemeral Reflex - <0.3ms cache reflex, <25ms in-process hook logic / ~120ms subprocess)**:
   - PreInvocation hook written in 100% Python Standard Library in `scripts/hook_runner.py`.
   - Reads fast RAM cache from `scripts/proven_traces.json` in <0.02ms.
   - Non-blocking append to `l1_staging_spool.jsonl` to eliminate SQLite lock contention on Windows NTFS.

2. **Tier 2 (L2 Hybrid Episodic Memory - <15ms retrieval, 0MB VRAM Tax)**:
   - Embedded SQLite database at `omni_memory.db` operating in **WAL mode** (`PRAGMA synchronous = NORMAL;`, `busy_timeout = 5000;`).
   - Hybrid search combining **Dual-Column FTS5 BM25** (`content_exact` weight 10.0 vs `content_folded` weight 1.0) with **CPU ONNX Embeddings** (`intfloat/multilingual-e5-small`, 384-dim, INT8 quantized, 0MB VRAM) via Reciprocal Rank Fusion ($k=20$).
   - *Graceful Degradation:* If `fastembed` is absent, Tier 2 automatically falls back to 100% pure-stdlib Dual-Column SQLite FTS5 BM25 without errors.

3. **Tier 3 (L3 Background Consolidator Daemon)**:
   - Out-of-band daemon `scripts/consolidator.py` drains staging records from the spool into the database.
   - Auto-promotes multi-hit patterns ($\ge 2$ successes) with automated bilingual tags into proven traces.
   - Applies Ebbinghaus stability decay, soft-archives stale records, and uses `PRAGMA wal_checkpoint(PASSIVE)` to completely prevent lock contention.

---

## 🛠️ Core Module Registry

| Component | Path | Description |
|---|---|---|
| **PreInvocation Hook** | `scripts/hook_runner.py` | Fast pre-flight interceptor injecting JIT skills, rules, and memory directives (<25ms in-process, ~120ms subprocess). |
| **JIT Skill Resolver** | `scripts/resolver.py` | Segment-aware skill and rule matching engine (<5ms warm, word-boundary synonyms, domain penalties). |
| **Autonomous Synthesizer** | `scripts/synthesizer.py` | Pipeline to author, AST-validate, sandbox-test, and promote new skills into the library. |
| **Skill Indexer** | `scripts/indexer.py` | High-speed zero-dependency indexer scanning 500+ skills across 4 sources in 0.12s with millisecond stale detection. |
| **Experiential Memory** | `scripts/experiential_memory.py` | Proven execution trace store with keyword stopword filtering and sub-millisecond retrieval. |
| **Memory Engine** | `scripts/memory_engine.py` | Hybrid search engine combining SQLite FTS5 BM25 with dense vector embeddings via RRF. |
| **Embedding Service** | `scripts/embedding_service.py` | Local CPU embedding generator using `fastembed` (`intfloat/multilingual-e5-small`, 384 dimensions). |
| **Memory Consolidator** | `scripts/consolidator.py` | Background daemon consuming staging logs, promoting multi-hit knowledge, and applying Ebbinghaus decay. |
| **Architecture Auditor** | `scripts/consult_critic.py` | External Red-Teaming critic client connecting to DeepSeek-V4.1-Flash for architecture review. |

---

## 🧪 Comprehensive Automated Testing & Empirical Verification

Omni-Skill Orchestrator maintains an exhaustive automated test suite with **100% pass rate (277/277 Tests PASS, 0 Skipped, 0 Flaked)**:

```bash
# 1. Run all core pytest and spec suites (117 tests, 0 skipped)
python -m pytest tests/ specs/001-omni-memory-v4/tests/ specs/002-deepseek-v41-auditor/tests/

# 2. Run Cluster 1–3 & Round 7 remediation verification suites (160 tests)
python scripts/test_cluster_1_remediation.py   # 69/69 passed (SQLite WAL, Outbox 2PC, SHA-256 Partitioning)
python scripts/test_cluster_2_remediation.py   # 51/51 passed (Hook <25ms SLA, HMAC Gate, Trust Lock, Lifecycle Epoch)
python scripts/test_cluster_3_remediation.py   # 17/17 passed (Resolver, AST Sandbox, CoW Stale-While-Revalidate)
python scripts/test_round_7_remediation.py     # 23/23 passed (Cross-Cluster Integration, Proven Recall & Edge Cases)

# 3. Run Real-World Scenarios Contract, 25-Query Golden Routing Eval & Empirical Benchmarks
python scripts/verify_real_world.py
# Result: 10/10 Scenarios PASS | Golden Routing Top-1 = 25/25 (100%), Top-3 = 25/25 (100%)
# Latency: Resolver warm: ~2-5ms | Hook core: ~12-22ms | SQLite FTS5: ~0.3-0.5ms
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
