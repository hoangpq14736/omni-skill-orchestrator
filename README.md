# 🧠 Omni-Skill Orchestrator

[![Agent Plugins 1.0.0](https://img.shields.io/badge/Spec-Agent%20Plugins%201.0.0-blue.svg)](https://agent-plugins.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)
[![Zero Dependency](https://img.shields.io/badge/Dependencies-0%20(Pure%20Stdlib)-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-8%2F8%20Passing-success.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Universal Autonomous Skill Intelligence for Google Antigravity & AI Coding Harnesses.**  
> *Stop memorizing slash commands. Let your AI agent autonomously detect stacks, resolve intent, arbitrate versions, and JIT-load 570+ (and up to 7,749+) skills with 0 token context waste.*

---

## ⚡ Why Omni-Skill?

Traditional agentic skill systems (such as Claude Code or Antigravity's active skills) suffer from a critical flaw: **Prompt Bloat vs. User Memory Fatigue**.

| Challenge | Traditional Skills / Active Plugins | Omni-Skill Orchestrator |
|---|---|---|
| **Context Overhead** | Loads 50–120 skills into System Prompt (**15,000–25,000 tokens**), hitting the 20k token ceiling and triggering silent exclusions. | **0 Tokens at idle!** Skills reside in an offline library (`skills_library/`) and are loaded Just-In-Time (JIT) only when needed. |
| **Activation Model** | Requires the user to remember and type `/command` or `/skill-name` manually. | **100% Autonomous Dual-Channel Detection** (Stack Markers + Semantic Intent). |
| **Conflict Handling** | Naive keyword matching can trigger obsolete or overly generic skills (e.g. `python-reviewer` over `fastapi-patterns`). | **4-Tier Arbitration Matrix** (Domain Specificity > SemVer Freshness > Scope Priority > Quality). |
| **Bilingual Support** | English only. | **Built-in Bilingual Semantic Mapper** (Vietnamese & English technical terms). |
| **Speed & Dependencies** | Heavy vector databases or slow embedding lookups. | **0 Dependencies (Pure Python Stdlib)**. Scans 496+ skills in **0.12s**, resolves in **1.1ms**. |

---

## 🏗️ Architecture

Omni-Skill works like an **Operating System Virtual Memory Manager (Paging / JIT)** for AI Agent capabilities:

```
                      ┌────────────────────────────────────┐
                      │    USER PROMPT & REPO WORKSPACE   │
                      └─────────────────┬──────────────────┘
                                        │
                    Dual-Channel Autonomous Detection
                                        │
            ┌───────────────────────────┴───────────────────────────┐
            ▼                                                       ▼
   [CHANNEL 1: STATIC]                                    [CHANNEL 2: DYNAMIC]
   Workspace Stack Markers                                Semantic Intent & Synonyms
   (package.json, Cargo.toml,                             (VI-EN Technical Mapper,
    requirements.txt, etc.)                                Task Keywords, Error Traces)
            │                                                       │
            └───────────────────────────┬───────────────────────────┘
                                        ▼
                      ┌────────────────────────────────────┐
                      │    4-TIER ARBITRATION ENGINE       │
                      │  1. Domain Specificity (FastAPI>Py)│
                      │  2. SemVer Freshness (v2.3 > v1.0) │
                      │  3. Scope Priority (Local > Global)│
                      │  4. Quality & Context Suitability  │
                      └─────────────────┬──────────────────┘
                                        ▼
                         [Top 1-3 Optimal Skills]
                                        │
                               JIT `read_file` (0.6ms)
                                        ▼
                      ┌────────────────────────────────────┐
                      │   EXECUTION VIA PONYTAIL SENIOR    │
                      │   Smallest Diff · YAGNI · No Bloat │
                      └────────────────────────────────────┘
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
```

---

## 🛠️ CLI Tools Included

* **`indexer.py`**: High-speed zero-dependency inverted indexer. Parses multi-line YAML frontmatters, extracts SemVer version clues, and builds an ultra-compact `registry.json`.
* **`resolver.py`**: Sub-2ms arbitration engine with bilingual Vietnamese-English mapping and stack detection.
* **`updater.py`**: Automated upstream watcher that monitors community skill repositories (`NousResearch/hermes-agent`, `DietrichGebert/ponytail`, `VoltAgent/awesome-agent-skills`) via GitHub API commit SHAs.

---

## 🧪 Testing

Omni-Skill includes a comprehensive unit test suite:

```bash
python -m unittest tests/test_engine.py
```

```text
........
----------------------------------------------------------------------
Ran 8 tests in 0.52s

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
