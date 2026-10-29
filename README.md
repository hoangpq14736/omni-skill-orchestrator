# 🧠 Omni-Kernel v2.5: Universal Autonomous Cognitive Operating System

[![Agent Plugins 1.0.0](https://img.shields.io/badge/Spec-Agent%20Plugins%201.0.0-blue.svg)](https://agent-plugins.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)
[![Zero Dependency](https://img.shields.io/badge/Dependencies-0%20(Pure%20Stdlib)-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-21%2F21%20Passing-success.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Universal Autonomous AI Cognitive Kernel for Google Antigravity & Advanced Agentic Harnesses.**  
> *Features PreInvocation Lifecycle Hook Automation, Non-Destructive Workspace Virtualization (Cursor/Claude/Gemini assimilation), JIT Skills, Inferred Rules, Dynamic MCP Tool Drivers, Human-like Cognitive Pre-Flight Deliberation (Lợi - Hại - Đủ - Thiếu), and Self-Bootstrapping Skill Synthesis with 0 static token overhead.*

---

## ⚡ Why Omni-Kernel v2.0?

Traditional agentic systems suffer from context bloat, rigid hardcoded rules, and inability to adapt to novel tasks.

| Challenge | Traditional Skills & Rules | Omni-Kernel v2.0 |
|---|---|---|
| **Context Overhead** | Loads 50–120 skills & static rules into System Prompt (**15,000–25,000 tokens**), hitting token ceilings and degrading model IQ. | **< 300 Tokens at idle!** Ring 0 Invariants stay lean; domain rules, skills, and tools are resolved Just-In-Time (JIT). |
| **Cognitive Reasoning** | Blind execution. Code without considering risks, security gotchas, or missing configurations. | **Cognitive Pre-Flight Loop (Lợi - Hại - Đủ - Thiếu)**: Evaluates value vs. risk, completeness, and implicit requirements before coding. |
| **Security & Invariants** | Hên xui: Chỉ bật bảo mật nếu user gõ từ "security". | **Kernel Ring 0 + Implicit Entailment**: Tự động suy ra luật bảo mật tương ứng theo domain (Web -> XSS/CORS; DB -> SQLi prevention). |
| **Adaptability & Learning** | Static hardcoded skills. Bó tay khi gặp công nghệ hoặc bo mạch lạ. | **Self-Bootstrapping Synthesizer**: Tự thiết kế, sandbox-test trong subprocess, và auto-promote skill mới vào thư viện. |
| **Multi-Resource Routing** | Chỉ quản lý skill đơn lẻ. MCP và Rules phải config tay. | **Unified Resource Resolution**: 1 lệnh giải quyết trọn bộ: Skill + Inferred Rule + Plug-and-Play MCP Driver. |
| **Speed & Dependencies** | Heavy vector databases or slow embedding lookups. | **0 Dependencies (Pure Python Stdlib)**. Scans 496+ skills in **0.10s**, resolves in **1.1ms**. |

---

## 🏗️ Architecture

Omni-Kernel v2.0 acts like a **Cognitive Operating System** for AI agents:

```
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
    (package.json, Cargo.toml,                             (VI-EN Technical Mapper,
     requirements.txt, etc.)                                Task Keywords, Error Traces)
             │                                                       │
             └──────────────────────────┬───────────────────────────┘
                                        ▼
                      ┌────────────────────────────────────┐
                      │    COGNITIVE ENTAILMENT GRAPH      │
                      │  - Inferred Domain Rules (Ring 3)  │
                      │  - Suggested MCP Tool Drivers      │
                      │  - 4-Tier Arbitration Matrix       │
                      └─────────────────┬──────────────────┘
                                        ▼
                      ┌────────────────────────────────────┐
                      │   COGNITIVE PRE-FLIGHT LOOP        │
                      │   🧠 LỢI (Value & Simplicity)      │
                      │   ⚠️ HẠI (Blast Radius & Risks)    │
                      │   ✅ ĐỦ (Completeness & Callers)   │
                      │   🔍 THIẾU (Implicit Invariants)   │
                      └─────────────────┬──────────────────┘
                                        │
             ┌──────────────────────────┴───────────────────────────┐
             ▼ (Existing Skill)                                     ▼ (Novel Task)
     JIT `read_file` (0.6ms)                               [SYNTHESIZER PIPELINE]
             │                                              Hypothesize -> Sandbox Test ->
             ▼                                              Auto-Promote (<150ms)
    [PONYTAIL EXECUTION]
    Smallest Diff · YAGNI · No Bloat
```

---

## 🚀 Performance Benchmarks

Measured on a standard developer workstation:

* **Inverted Indexing:** 496 skills across 4 sources in **0.12s** (`indexer.py`).
* **Cache Freshness Check:** Stale check via `mtime` in **0.58ms** (`is_registry_stale()`).
* **Intent & Stack Resolution:** Bilingual query to ranked skill candidate in **1.12ms** (`resolver.py`).
* **Context Token Footprint:** **0 Tokens** in the static system prompt.

---

## 📦 Installation

### Method 1: Antigravity Plugin (Recommended)

1. Clone or copy this repository into your plugins directory:
   ```bash
   git clone https://github.com/<your-username>/omni-skill-orchestrator.git ~/.gemini/config/plugins/omni-skill-orchestrator
   ```
2. Validate and enable the plugin:
   ```bash
   agy plugin validate ~/.gemini/config/plugins/omni-skill-orchestrator
   agy plugin enable omni-skill-orchestrator
   ```

### Method 2: Standalone CLI / Python Engine

You can also use Omni-Skill as an independent, standalone skill resolver in any Python project or CI/CD pipeline:

```bash
# Query optimal skills for an intent
python scripts/resolver.py --intent "chuyển ảnh chụp hóa đơn sang bảng excel"

# Query optimal skills for a workspace
python scripts/resolver.py --workspace "./my-rust-project" --intent "test firmware UART"

# Reinforce feedback (Self-Learning / Meta-Evolution)
python scripts/resolver.py --intent "canvas game" --workspace "./my-game" --feedback generative_ui

# Synthesize & sandbox-test a new skill
python scripts/synthesizer.py --name "modbus-rtu-reader" --desc "Serial protocol reader for industrial sensors" --test "assert True"

# View self-learning stats
python scripts/resolver.py --learn-stats

# Reset learned memory
python scripts/resolver.py --reset-learning
```

---

## 🛠️ CLI Tools Included

* **`hook_runner.py`**: Global Antigravity `PreInvocation` Lifecycle Hook runner. Intercepts incoming turns in <50ms and injects ephemeral Cognitive Pre-Flight directives without modifying `transcript.jsonl`.
* **`assimilator.py`**: Non-destructive Workspace Virtualization Engine. Scans foreign repositories and assimilates `.cursorrules`, `GEMINI.md`, `CLAUDE.md`, and local skills into the virtual registry on the fly.
* **`resolver.py`**: Sub-2ms Unified Resource Resolver (Skills, Inferred Rules, MCP Drivers, and Cognitive Pre-Flight matrix).
* **`synthesizer.py`**: Autonomous Skill & Tool Synthesizer with subprocess sandbox validation and auto-promotion to `skills_library`.
* **`indexer.py`**: High-speed zero-dependency inverted indexer. Parses multi-line YAML frontmatters, extracts SemVer version clues, and builds an ultra-compact `registry.json` in 0.10s.
* **`updater.py`**: Automated upstream watcher that monitors community skill repositories (`NousResearch/hermes-agent`, `DietrichGebert/ponytail`, `VoltAgent/awesome-agent-skills`) via GitHub API commit SHAs.

---

## 🧪 Testing

Omni-Kernel includes an automated unit test suite covering 20 full scenarios:

```bash
python tests/test_engine.py
```

```text
....................
----------------------------------------------------------------------
Ran 20 tests in 1.78s

OK
```

---

## 🤝 Philosophy: Built on Ponytail

Omni-Skill is built following the **Ponytail Philosophy (Lazy Senior Developer Mode)**:
* **The best code is the code never written.**
* Zero unnecessary dependencies (100% standard library `os`, `json`, `re`, `time`, `urllib`).
* Shortest working diff wins.
* No bloated abstractions or "for later" wrappers.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
