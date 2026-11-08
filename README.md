# 🧠 Omni-Skill Orchestrator v4.1: Adaptive JIT Harness & Reflex Memory for AI Agents

[![Agent Plugins 1.0.0](https://img.shields.io/badge/Spec-Agent%20Plugins%201.0.0-blue.svg)](https://agent-plugins.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)
[![Zero Dependency Kernel](https://img.shields.io/badge/Dependencies-0%20(Pure%20Stdlib%20Core)-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-277%2F277%20Passing-success.svg)]()
[![Council Gate](https://img.shields.io/badge/DeepSeek%20Council%20Gate-APPROVED-brightgreen.svg)](docs/audits/omni_kernel_v41_final_approved_verdict.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) • [Tiếng Việt](README.vi.md)

> **A lightweight, local-first orchestration harness for Google Antigravity, Claude Code, Cursor, and AI coding agents.**  
> *Equipped with sub-millisecond JIT skill routing, Tri-Tier episodic memory (SQLite WAL + Dual-Column FTS5 BM25 + 384-dim CPU ONNX embeddings), autonomous skill synthesis, Graphify-grade codebase topology (Omni-Graph), and decoupled architecture gatekeeping — with zero static prompt token bloat.*

---

## 🎯 What is Omni-Skill Orchestrator?

Omni is **not** a standalone autonomous coding agent (like Aider, OpenCode, or OpenHands). Instead, it is an **intelligent pre-flight harness and reflex layer** that sits in front of your primary agent (e.g., Antigravity, Claude Code):

1. **Stops System Prompt Bloat**: Rather than injecting 50–120 static skills and rules (costing 15,000–25,000 tokens per chat turn), Omni indexes 500+ skills in **0.12s** and injects only the top 1–3 relevant skills and rules **Just-In-Time (< 300 tokens)**.
2. **Cross-Session Reflex Memory**: Automatically captures successful fixes, indexes them into SQLite WAL with FTS5 BM25 and 384-dim CPU ONNX dense vectors (`intfloat/multilingual-e5-small`), and recalls matching proven solutions in **< 0.3ms**.
3. **Graphify-Grade Codebase Topology (Omni-Graph)**: Zero-dependency relational call graph stored in workspace-local SQLite WAL (`.omni/codebase_graph.db`). Delivers **Hardened Signature Contract Guard**, **Lifecycle Registration Guard**, **Blast Radius Engine (<2ms)**, and an **Interactive Vis.Network 9.1.6 Visualizer** with Fermat spiral seeding and zero perpetual jitter.
4. **Universal Polyglot Extractor**: Built for the fluid "vibe coder" with zero external native compilation requirements. Directly maps Python, JavaScript/TypeScript, Go, Rust, SQL, Shell, Markdown docs, and configs.
5. **Autonomous Skill Synthesis**: When encountering novel technical domains, Omni authors candidate `SKILL.md` documents, runs static AST security analysis, validates them in an isolated sandbox, and atomically promotes them into the local library.
6. **Decoupled Architecture Gatekeeper**: Inspects architecture intents (RFC, SDD, major diffs) in `< 25ms` in-process logic (`~120ms` full subprocess turnaround on Windows) without blocking the chat loop with synchronous cloud calls.

---

## ⚡ Feature Comparison

| Capability | Static Skills & Prompt Bloat | Omni-Skill Orchestrator v4.1 |
|---|---|---|
| **Context Overhead** | Injects 50–120 static skills (**15,000–25,000 tokens**), degrading model IQ and hitting context limits. | **< 300 Tokens at idle!** Invariants stay lean; domain skills, rules, and tools are resolved Just-In-Time (JIT). |
| **Routing Accuracy** | Naive substring matching often misroutes to irrelevant skills. | **Segment-Aware Scoring + Word Boundaries**: Differentiates domain subjects (`docker`, `sqlite`, `postgres`) from generic actions (`fix`, `debug`, `guide`). Achieves **100% Top-1 & Top-3 accuracy** on the 25-query Golden Benchmark. |
| **Episodic Memory** | Flat JSON files that corrupt or slow down chat, or heavy SaaS vector DBs. | **Tri-Tier Omni-Memory**: Tier 1 non-blocking RAM spool (<0.3ms); Tier 2 Embedded SQLite WAL with Dual-Column FTS5 BM25 + 384-dim CPU ONNX Embeddings (0MB VRAM tax); Tier 3 Consolidator with Ebbinghaus decay. |
| **Codebase Topology (Omni-Graph)** | No structural awareness or heavy 50MB JSON dumps that choke context. | **Relational SQLite WAL Topology**: Indexed recursive CTEs compute caller/callee blast radius in <2ms. Enforces Hardened Signature Contract Guards (PEP 570, kwargs, async unawaited) and exports interactive Vis.Network 9.1.6 diagrams with zero perpetual movement. |
| **Polyglot Parsing** | Hardcoded to single language or fragile C-based compilers. | **Universal Polyglot Extractor (Zero-Dependency)**: Native stdlib AST for Python + regex streaming extractors for JS/TS, Go, Rust, SQL, Shell, and Markdown. |
| **Skill Synthesis** | Manual authoring required for every new library or tool. | **Autonomous Pipeline**: `scripts/synthesizer.py` authors templates, runs AST syntax checks, validates assertions in sandbox, and auto-indexes in <150ms. |
| **Architectural Gatekeeping** | Internal subagents create an "Echo Chamber", blindly approving each other's hallucinations. | **Decoupled Council Gate (DeepSeek-V4.1-Flash)**: Verified via HMAC-SHA256 signatures and SHA-256 target hashes without blocking hook turnaround. |
| **Core Dependencies** | Relies on heavy frameworks and unstable cloud services. | **Pure Python Standard Library Core** for Kernel, Hook, SQLite FTS5, and Omni-Graph (0 external native dependencies). |

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
                      │  - Omni-Graph: Pre-flight blast radius & contract risk │
                      │  - Gatekeeper: HMAC-SHA256 audit artifact verification │
                      └───────────────────────────┬────────────────────────────┘
                                                  │ (Injects <300 tokens JIT context)
                                                  ▼
                                      ┌───────────────────────┐
                                      │  INFORMED AGENT TURN  │
                                      └───────────────────────┘
```

---

## 🌐 Omni-Graph Architecture (Graphify-Grade Topology)

Omni-Graph maintains physical and logical **Zero-Conflict Duality**:
- **Global Cognitive Memory**: Stored in `omni_memory.db` for multi-session learning, proven solutions, and cross-project knowledge.
- **Local Codebase Topology**: Stored in `<workspace>/.omni/codebase_graph.db` (SQLite WAL mode) strictly isolated per repository.

### Key Components:
1. **Relational Graph Storage (`scripts/omni_graph/storage.py`)**:
   - Normalized relational tables: `nodes`, `signatures`, `edges`, `lifecycle_hooks`, and `codebase_files_meta`.
   - Covered with 7 B-Tree indexes for instantaneous traversals.
2. **Two-Tier Change Detection (`scripts/omni_graph/fingerprint.py`)**:
   - Tier 1: Filesystem `mtime` and `size_bytes` checking in **< 2ms** for 100+ files.
   - Tier 2: Cryptographic SHA-256 dirty check when timestamps mismatch.
3. **Hardened Signature Contract Guard (`scripts/omni_graph/validator.py`)**:
   - Method receiver normalization (auto-strips `self` and `cls`).
   - Strict validation of PEP 570 positional-only args, keyword-only args, and unexpected parameters.
   - Catches broken caller interfaces before changes are executed.
4. **Interactive Vis-Network Visualizer (`scripts/omni_graph/visualizer.py`)**:
   - Vis.Network 9.1.6 embedding with Tableau 10 color palette.
   - Fermat spiral seed positions ($x = 35 \sqrt{i} \cos(2.4 i)$, $y = 35 \sqrt{i} \sin(2.4 i)$).
   - Automatic physics stabilization freeze at 200 iterations (**zero perpetual motion/jitter**).
   - Sidebar with Theme toggle (Dark/Light/System), live search autocomplete, node inspector, and community visibility filters.

---

## 🛠️ Core Module Registry

| Component | Path | Description |
|---|---|---|
| **PreInvocation Hook** | `scripts/hook_runner.py` | Fast pre-flight interceptor injecting JIT skills, rules, and memory directives (<25ms in-process, ~120ms subprocess). |
| **JIT Skill Resolver** | `scripts/resolver.py` | Segment-aware skill and rule matching engine (<5ms warm, word-boundary synonyms, domain penalties). |
| **Omni-Graph CLI** | `scripts/omni_graph.py` | Unified driver for codebase scanning, contract validation, blast radius, and visualizer generation. |
| **Omni-Graph Engine** | `scripts/omni_graph/` | Full relational graph engine: `storage.py`, `fingerprint.py`, `visitor.py`, `validator.py`, `traversal.py`, `visualizer.py`. |
| **Autonomous Synthesizer** | `scripts/synthesizer.py` | Pipeline to author, AST-validate, sandbox-test, and promote new skills into the library. |
| **Skill Indexer** | `scripts/indexer.py` | High-speed zero-dependency indexer scanning 500+ skills across 4 sources in 0.12s with millisecond stale detection. |
| **Experiential Memory** | `scripts/experiential_memory.py` | Proven execution trace store with keyword stopword filtering and sub-millisecond retrieval. |
| **Memory Engine** | `scripts/memory_engine.py` | Hybrid search engine combining SQLite FTS5 BM25 with dense vector embeddings via RRF. |
| **Embedding Service** | `scripts/embedding_service.py` | Local CPU embedding generator using `fastembed` (`intfloat/multilingual-e5-small`, 384 dimensions). |
| **Memory Consolidator** | `scripts/consolidator.py` | Background daemon consuming staging logs, promoting multi-hit knowledge, and applying Ebbinghaus decay. |
| **Architecture Auditor** | `scripts/consult_critic.py` | External Red-Teaming critic client connecting to DeepSeek-V4.1-Flash for architecture review. |

---

## 🧪 Comprehensive Automated Testing & Empirical Verification

Omni-Skill Orchestrator maintains an exhaustive automated test suite with **100% pass rate**:

```bash
# 1. Run core test suites & DeepSeek auditor gates (45 tests PASS)
python -m pytest specs/002-deepseek-v41-auditor/tests/

# 2. Run Omni-Graph empirical challenge & contract validator (16/16 PASS)
python tests/test_omni_graph_validator_empirical.py

# 3. Run Omni-Graph live workspace integration suite (2/2 PASS)
python tests/test_omni_graph_live.py

# 4. Scan and visualize any workspace instantly
python scripts/omni_graph.py --workspace "." --scan --visualize
```

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
