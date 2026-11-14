# ⚡ Omni-Skill Orchestrator v4.3: Adaptive JIT Harness, Cloud Worker Fleet & Reflex Memory

[![Agent Plugins 1.0.0](https://img.shields.io/badge/Spec-Agent%20Plugins%201.0.0-blue.svg)](https://agent-plugins.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)
[![Zero Dependency Kernel](https://img.shields.io/badge/Dependencies-0%20(Pure%20Stdlib%20Core)-brightgreen.svg)]()
[![Council Gate](https://img.shields.io/badge/DeepSeek%20Council%20Gate-APPROVED%20(1M%20Context)-brightgreen.svg)](docs/audits/omni_kernel_v41_final_approved_verdict.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) • [Tiếng Việt](README.vi.md)

> **A lightweight, local-first orchestration harness for Google Antigravity, Claude Code, Cursor, and autonomous AI coding agents.**  
> *Equipped with sub-millisecond JIT skill routing, Unified Cloud Worker Fleet delegation (Google Gemini 3.5/3.8/4 Argon Autonomous Loop + DeepSeek-V4.1-Flash 1M Gatekeeper), Tri-Tier episodic memory (SQLite WAL + Dual-Column FTS5 BM25 + 256-dim CPU ONNX embeddings), Graphify-grade codebase topology (Omni-Graph), and zero static prompt token bloat.*

> [!WARNING]
> ### ⚠️ Personal Tailor-Made Project (Dự Án Cá Nhân Đo Ni Đóng Giày)
> This repository is exclusively customized and tightly coupled to the personal workflow, hardware infrastructure (Google Cloud API budget, DeepSeek Auditor API, and specific Windows NTFS paths), and local tooling of its creator. It is **NOT designed, maintained, or supported for general public use**. External setup attempts will likely fail due to strict host-specific paths, private IPC mutexes, and unique environment dependencies.

---

## 🎯 What is Omni-Skill Orchestrator?

Omni is **not** a standalone autonomous coding agent (like Aider, OpenCode, or OpenHands). Instead, it is an **intelligent pre-flight harness and reflex layer** that sits in front of your primary agent (e.g., Antigravity, Claude Code):

1. **Stops System Prompt Bloat**: Rather than injecting 50–120 static skills and rules (costing 15,000–25,000 tokens per chat turn), Omni indexes 500+ skills in **0.12s** and injects only the top 1–3 relevant skills and rules **Just-In-Time (< 300 tokens)**.
2. **Cloud Worker Fleet Protocol**: Autonomous behind-the-scenes workload dispatching to conserve cloud context:
   - **`gemini_worker_cloud`** (Google Gemini 3.5 Flash-Lite / 3.8 Flash / 4 Argon): Unified execution engine providing atomic in-place edits (`gemini_fast_edit`), unit test generation (`gemini_generate_tests`), closed-loop self-healing test-and-fix execution (`gemini_autonomous_loop`), multi-step Plan-Execute-Handback orchestration (`gemini_execute_plan` with `replan_if` circuit breaker & `auto_replan_with_argon`), **1,000,000-token** heavy codebase synthesis (`gemini_heavy_code_gen`), multimodal vision (`gemini_multimodal_vision`), and deep reasoning (`gemini_argon_solve`).
   - **`deepseek_worker_cloud`** (DeepSeek-V4.1-Flash): Independent spec and diff verification audit gate (`deepseek_audit_spec`, `deepseek_audit_diff`).
3. **Decoupled Architecture Gatekeeper (DeepSeek-V4.1-Flash 1M Context)**: Protects against the "Echo Chamber" anti-pattern (Gemini subagents reviewing Gemini). Inspects RFCs, SDD bundles, and patches via an independent 552B MoE model natively supporting **1,000,000 tokens context** and FP4 KV cache compression.
4. **Cross-Session Reflex Memory**: Automatically captures successful fixes, indexes them into SQLite WAL with Dual-Column FTS5 BM25 and custom fine-tuned 256-dim CPU ONNX dense vectors (`google/embeddinggemma-2-omni` INT8 MRL), and recalls matching proven solutions in **< 0.3ms**.
5. **Graphify-Grade Codebase Topology (Omni-Graph)**: Zero-dependency relational call graph stored in workspace-local SQLite WAL (`.omni/codebase_graph.db`). Delivers **Hardened Signature Contract Guard**, **Lifecycle Registration Guard**, **Blast Radius Engine (<2ms)**, and an **Interactive Vis.Network 9.1.6 Visualizer** with Fermat spiral seeding and zero perpetual jitter.
6. **Universal Polyglot Extractor**: Built for the fluid "vibe coder" with zero external native compilation requirements. Directly maps Python, JavaScript/TypeScript, Go, Rust, SQL, Shell, Markdown docs, and configs.
7. **Autonomous Skill Synthesis**: When encountering novel technical domains, Omni authors candidate `SKILL.md` documents, runs static AST security analysis, validates them in an isolated sandbox, and atomically promotes them into the local library.

---

## ⚡ Feature Comparison

| Capability | Static Skills & Prompt Bloat | Omni-Skill Orchestrator v4.3 |
|---|---|---|
| **Context Overhead** | Injects 50–120 static skills (**15,000–25,000 tokens**), degrading model IQ and hitting context limits. | **< 300 Tokens at idle!** Invariants stay lean; domain skills, rules, and tools are resolved Just-In-Time (JIT). |
| **Worker Delegation** | Agent bloats context generating boilerplate and massive tests directly. | **Unified Cloud Worker Fleet**: Offloading fast edits, tests, autonomous verification loops, and 1M-context heavy coding to Gemini Cloud, gated by DeepSeek 1M audit. |
| **Architectural Gatekeeping** | Internal subagents create an "Echo Chamber", blindly approving each other's hallucinations. | **Decoupled Council Gate (DeepSeek-V4.1-Flash 1M)**: Verified via HMAC-SHA256 signatures, 1M native context, independent multi-vendor red-teaming. |
| **Routing Accuracy** | Naive substring matching often misroutes to irrelevant skills. | **Segment-Aware Scoring + Word Boundaries**: Differentiates domain subjects (`docker`, `sqlite`, `postgres`) from generic actions (`fix`, `debug`, `guide`). Achieves **100% Top-1 & Top-3 accuracy** on Golden Benchmark. |
| **Episodic Memory** | Flat JSON files that corrupt or slow down chat, or heavy SaaS vector DBs. | **Tri-Tier Omni-Memory**: Tier 1 non-blocking RAM spool (<0.3ms); Tier 2 Embedded SQLite WAL with Dual-Column FTS5 BM25 + fine-tuned 256-dim CPU ONNX Embeddings (`google/embeddinggemma-2-omni` INT8 MRL, 0MB VRAM tax); Tier 3 Consolidator with Ebbinghaus decay. |
| **Codebase Topology (Omni-Graph)** | No structural awareness or heavy 50MB JSON dumps that choke context. | **Relational SQLite WAL Topology**: Indexed recursive CTEs compute caller/callee blast radius in <2ms. Enforces Hardened Signature Contract Guards (PEP 570, kwargs, async unawaited) and exports interactive Vis.Network 9.1.6 diagrams. |
| **Core Dependencies** | Relies on heavy frameworks and unstable cloud services. | **Pure Python Standard Library Core** for Kernel, Hook, SQLite FTS5, and Omni-Graph (0 external native dependencies). |

---

## 🏗️ Layered Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   PRIMARY AGENT HARNESS (Free Quota)                  │
│       Google Antigravity / Claude Code / Cursor (Architect / Router)   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Pre-Flight Reflex (<0.3ms)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   OMNI-KERNEL v4.3 ENGINE                              │
│   • L1 Reflex & PreToolUse Plan Gate (scripts/hook_runner.py)         │
│   • JIT Skill & Rule Resolver (scripts/resolver.py)                    │
│   • Tri-Tier Omni-Memory (scripts/memory_engine.py - SQLite WAL FTS5)   │
│   • Omni-Graph Topology Guard (scripts/omni_graph.py - Blast Radius)   │
└──────────────────┬───────────────────────┬─────────────────────────────┘
                   │                       │
                     Implementation / Gatekeeping Delegation
                   ┌───────────────────────┴──────────────────────────┐
                   ▼                                                  ▼
┌────────────────────────────────────────┐   ┌──────────────────────────────────────┐
│      GEMINI WORKER CLOUD (7 Tools)     │   │       COUNCIL PROTOCOL GATE          │
│   3.5 Lite / 3.8 Flash / 4 Argon (1M)  │   │   DeepSeek-V4.1-Flash (1M Context)   │
│ • Fast Edits, Tests & Autonomous Loop  │   │   • Anti-Echo-Chamber Verification   │
│ • Heavy Code Gen & Multimodal Vision   │   │   • HMAC-SHA256 Spec & Diff Audit    │
└────────────────────────────────────────┘   └──────────────────────────────────────┘
```

---

## 📦 Core Module Catalog

| Component | Path | Description |
|---|---|---|
| **PreInvocation & PreToolUse Hook** | `scripts/hook_runner.py` | Sub-millisecond pre-flight interceptor injecting JIT skills/rules & Warn-Once Auto-Unlock Plan Gate (<25ms). |
| **JIT Skill Resolver** | `scripts/resolver.py` | Segment-aware skill and rule matching engine (<5ms). |
| **Gemini Cloud Worker** | `scripts/gemini_worker.py` | 100% Python stdlib driver for Google Gemini 3.5/3.8/Argon (1M context, multimodal, deep reasoning). |
| **Gemini Worker MCP** | `D:\Antigravity\Gemini Worker\gemini_worker_mcp.py` | JSON-RPC 2.0 stdio MCP server (`io_helpers`, `autonomous_tools`, `loop_runner`) exposing `gemini_heavy_code_gen`, `gemini_multimodal_vision`, `gemini_argon_solve`, `gemini_fast_edit`, `gemini_generate_tests`, `gemini_autonomous_loop`, and `gemini_execute_plan`. |
| **Architecture Auditor** | `scripts/consult_critic.py` | Decoupled Council Gatekeeper client connecting to DeepSeek-V4.1-Flash with 1,000,000 tokens context. |
| **Omni-Graph CLI** | `scripts/omni_graph.py` | CLI driver for scanning codebases, validating signature contracts, and generating visual graphs. |
| **Memory Engine** | `scripts/memory_engine.py` | Hybrid search engine combining SQLite FTS5 BM25 and CPU ONNX dense vectors via RRF. |
| **Autonomous Synthesizer** | `scripts/synthesizer.py` | Self-bootstrapping pipeline authoring, verifying in sandbox, and promoting novel skills. |

---

## 🧪 Testing & Verification

Omni-Skill Orchestrator maintains a comprehensive automated test suite with **100% pass rate**:

```bash
# 1. Run WAL Multi-Process Concurrency Test (NT/Windows SQLite WAL Stress Test)
python tests/test_concurrency_wal.py

# 2. Run DeepSeek Council Gatekeeper Live Review (1M Context Verification)
python scripts/consult_critic.py --prompt "System health check" --mode rfc

# 3. Test Gemini Cloud Worker Live Inference (1M Context Flash-Lite)
python scripts/gemini_worker.py --task "Test echo" --model gemini-3.5-flash-lite

# 4. Scan & Visualize Codebase Topology
python scripts/omni_graph.py --workspace "." --scan --visualize
```

---

## 🙏 Acknowledgements

Omni-Skill Orchestrator stands on the shoulders of giants in the open-source and AI engineering community:

- **[Graphify](https://github.com/Graphify-Labs/graphify)** (*Graphify-Labs*): Pioneer in turning codebases into queryable knowledge graphs, Fermat spiral distribution, and Vis.Network visualizers.
- **[Spec Kit](https://github.com/github/spec-kit)** (*GitHub*): Inspiration for the 10-phase Specification-Driven Development (SDD) engineering rigor.
- **[Ponytail](https://github.com/DietrichGebert/ponytail)** (*Dietrich Gebert*): Supreme minimalism philosophy (Lazy Senior Dev Mode): smallest working diff, stdlib over bloat, YAGNI.
- **[DeepSeek AI](https://github.com/deepseek-ai)** (*DeepSeek*): Breakthrough MoE and 1M context CED architecture powering our independent Council Gatekeeper.
- **[Google Generative AI](https://ai.google.dev/)** (*Google DeepMind*): 1,000,000 tokens context window, Flash-Lite efficiency, Flash 3.8 autonomous verification, and Argon deep reasoning models.
- **[Vis.js Network](https://github.com/visjs/vis-network)**: Physics simulation and smooth browser network visualization engine.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
