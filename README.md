# 🧠 Omni-Kernel v3.0: Universal Autonomous Cognitive Operating System

[![Agent Plugins 1.0.0](https://img.shields.io/badge/Spec-Agent%20Plugins%201.0.0-blue.svg)](https://agent-plugins.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)
[![Zero Dependency](https://img.shields.io/badge/Dependencies-0%20(Pure%20Stdlib)-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-30%2F30%20Passing-success.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) • [Tiếng Việt](README.vi.md)

> **Universal Autonomous AI Cognitive Kernel for Google Antigravity, Claude Code, Cursor, and Agentic Frameworks.**  
> *Features Dual-Tier Cognitive Routing (L1 Reflex vs. L2 Strategist Subagent), PreInvocation Lifecycle Hook Automation, Non-Destructive Workspace Virtualization (Cursor/Claude/Gemini assimilation), JIT Skills, Inferred Rules, Dynamic MCP Tool Drivers, and Self-Bootstrapping Skill Synthesis with zero static token overhead.*

---

## ⚡ Why Omni-Kernel?

Traditional AI agent configurations suffer from static context bloat, fragile hardcoded prompts, runaway token consumption, and an inability to adapt to unfamiliar technical stacks.

| Dimension | Traditional Agents & Static Skills | Omni-Kernel v3.0 |
|---|---|---|
| **Context Overhead** | Injects 50–120 skills & static rules into System Prompt (**15,000–25,000 tokens**), hitting context ceilings and degrading model IQ. | **< 300 Tokens at idle!** Ring 0 Invariants stay lean; domain rules, skills, and tools are resolved Just-In-Time (JIT). |
| **Cognitive Routing** | Single monolithic execution loop. Burns premium model tokens on trivial commands. | **Dual-Tier Cognitive Routing**: L1 Fast Reflex (0-token, <1ms) handles ~85% of tasks; L2 Strategist Subagent activates only for complex architecture/debugging. |
| **Security & Invariants** | Unreliable: Security constraints only activate if the user explicitly mentions "security". | **Cognitive Entailment Graph**: Automatically infers mandatory security invariants per domain (Web $\rightarrow$ XSS/CORS; DB $\rightarrow$ Parameterized SQL; Docker $\rightarrow$ Non-root user). |
| **Workspace Portability** | Requires manual reconfiguration for every repository and different IDE conventions. | **Workspace Assimilator**: Non-destructively scans and ingests `.cursorrules`, `GEMINI.md`, `CLAUDE.md`, and local skills in <1ms without touching source files. |
| **Adaptability & Learning** | Static hardcoded skills. Fails when facing novel frameworks or custom hardware. | **Self-Bootstrapping Synthesizer**: Generates candidate skills, validates them in an isolated subprocess sandbox, and auto-promotes them to the library. |
| **Speed & Dependencies** | Heavy external vector databases, embedding APIs, or fragile runtime wrappers. | **0 External Dependencies (Pure Python Stdlib)**. Scans 500+ skills in **0.10s**, resolves in **~1ms** at **1,000+ QPS**. |

---

## 🏗️ Architecture

Omni-Kernel operates as a deterministic, sub-millisecond **Cognitive Middleware** beneath any LLM:

```text
                      ┌────────────────────────────────────┐
                      │    USER PROMPT & REPO WORKSPACE   │
                      └─────────────────┬──────────────────┘
                                        │
                         Dual-Channel Autonomous Detection
                                        │
              ┌──────────────────────────┴───────────────────────────┐
              ▼                                                       ▼
     [CHANNEL 1: STATIC]                                    [CHANNEL 2: DYNAMIC]
     Workspace Stack Markers                                Semantic Intent & Synonyms
     (package.json, Cargo.toml,                             (Bilingual EN-VI Mapper,
      requirements.txt, etc.)                                Task Keywords, Error Traces)
              │                                                       │
              └──────────────────────────┬───────────────────────────┘
                                         ▼
                      ┌────────────────────────────────────┐
                      │    COGNITIVE ENTAILMENT GRAPH      │
                      │  - Inferred Domain Rules (Ring 3)  │
                      │  - Suggested MCP Tool Drivers      │
                      │  - 4-Tier Arbitration Matrix       │
                      │  - Complexity Score (0-100)        │
                      └─────────────────┬──────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼ (Score < 50)                                  ▼ (Score >= 50)
      ┌────────────────────────┐                     ┌────────────────────────┐
      │ TIER 1: L1 FAST REFLEX │                     │ TIER 2: L2 STRATEGIST  │
      │ ⚡ Quota Guard Locked   │                     │ 🧠 Subagent Delegation │
      │ 0 Extra Tokens, <50ms  │                     │ 'omni-strategist' live │
      │ Ephemeral Pre-Flight   │                     │ Deep System 2 Planning │
      └────────────────────────┘                     └────────────────────────┘
```

---

## 🚀 Performance Benchmarks

Measured on a standard developer workstation (AMD/Intel, Windows/Linux/macOS):

* **Inverted Indexing:** 501+ skills across 4 sources indexed in **0.10s** (`indexer.py`).
* **Cache Freshness Check:** Stale cache detection via filesystem `mtime` in **0.42ms** (`is_registry_stale()`).
* **Intent & Stack Resolution:** Bilingual query to ranked skill candidate in **0.92ms** (`resolver.py`).
* **Lifecycle Hook Latency:** Process spawn, stdin parse, resolution, and stdout injection in **< 45ms** (`hook_runner.py`).
* **Throughput:** **1,078 Queries / Second** on a single thread.
* **Accuracy:** **85.0%** Top-1 Accuracy, **95.0%** Top-3 Accuracy, **100%** Inferred Rule Alignment across 20 technical domains.

---

## 📦 Installation

### Method 1: Google Antigravity Plugin (Recommended)

1. Clone this repository into your customizations plugin directory:
   ```bash
   git clone https://github.com/hoangpq14736/omni-skill-orchestrator.git ~/.gemini/config/plugins/omni-skill-orchestrator
   ```
2. Enable the plugin via Antigravity CLI or UI:
   ```bash
   agy plugin enable omni-skill-orchestrator
   ```
3. *Zero configuration needed.* The global `PreInvocation` hook automatically activates before each turn.

### Method 2: Standalone CLI & Cross-Platform Middleware

Omni-Kernel runs anywhere Python 3.10+ is installed:

```bash
# Query optimal skills for an intent
python scripts/resolver.py --intent "optimize postgresql queries and add migration"

# Query with workspace stack detection
python scripts/resolver.py --workspace "./my-rust-project" --intent "write integration test"

# Inspect the most recent hook activation (telemetry dashboard)
python scripts/resolver.py --last

# Reinforce feedback (Self-Learning / Meta-Evolution)
python scripts/resolver.py --intent "canvas game" --workspace "./my-game" --feedback generative_ui

# Synthesize & sandbox-test a new skill candidate
python scripts/synthesizer.py --name "modbus-rtu-reader" --desc "Serial protocol reader for industrial sensors" --test "assert True"

# View meta-learning statistics
python scripts/resolver.py --learn-stats
```

---

## 🛠️ Included Components

| Component | Path | Description |
|---|---|---|
| **PreInvocation Hook** | `scripts/hook_runner.py` | Intercepts turns in <45ms. Injects ephemeral cognitive pre-flight directives without bloating `transcript.jsonl`. |
| **Dual-Tier Router** | `scripts/dual_tier.py` | Computes task complexity (0-100). Enforces Quota Guard on simple queries (L1) and elevates to L2 Strategist only when needed. |
| **Experiential Memory** | `scripts/experiential_memory.py` | Cross-session memory recalling proven code fixes and verified CLI execution traces in <0.3ms without re-reasoning. |
| **Progress & Growth Reporter** | `scripts/reporter.py` | Generates executive Markdown & JSON reports detailing operational KPIs, token savings, top skills, and knowledge growth. |
| **Omni-MCP Virtual Bus** | `scripts/mcp_gateway.py` | Dynamic Tool Multiplexer & JIT Gateway. Indexes 80+ tools across 25 MCP servers, routes queries in <0.3ms, and validates parameters. |
| **Workspace Assimilator** | `scripts/assimilator.py` | Non-destructively scans any repository for `.cursorrules`, `GEMINI.md`, `CLAUDE.md`, and local skills, prioritizing them with `SCOPE_PRIORITY = 40`. |
| **Unified Resolver** | `scripts/resolver.py` | Sub-millisecond arbitration engine for Skills, Inferred Rules, MCP Drivers, and Cognitive Assessment. |
| **Skill Synthesizer** | `scripts/synthesizer.py` | Autonomous skill authoring pipeline with subprocess sandbox execution and auto-promotion. |
| **Inverted Indexer** | `scripts/indexer.py` | High-speed YAML frontmatter parser and inverted index generator. |
| **Subagent Definition** | `agents/omni-strategist.json` | Dedicated autonomous strategic planning and systematic debugging subagent archetype. |

---

## 🧪 Testing

Omni-Kernel maintains a comprehensive automated test suite with **100% pass rate**:

```bash
python tests/test_engine.py
```

```text
............................
----------------------------------------------------------------------
Ran 28 tests in 2.02s

OK
```

Run the pre-release benchmark suite:
```bash
python tests/benchmark_suite.py
```

---

## 🤝 Philosophy: Built on Ponytail

Omni-Kernel strictly adheres to the **Ponytail Engineering Philosophy**:
* **The best code is the code never written.** Smallest complete working diff wins.
* Zero unnecessary external dependencies (100% Python Standard Library: `os`, `json`, `re`, `time`, `urllib`).
* Immutability first, fail loudly with diagnostic context, and never silently swallow exceptions.
* JIT ephemeral context injection over permanent static prompt bloat.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
