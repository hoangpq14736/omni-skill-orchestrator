---
name: omni-skill-orchestrator
description: >-
  Universal AI Skill & Plugin Intelligence: Automatically discovers, resolves, and auto-activates the optimal skill or agent for any project or task across 550+ (and up to 7,749+) installed plugins, active skills, library skills, and builtin tools with Tri-Tier Omni-Memory v4.1, Omni-Auditor Council Gate, and sub-millisecond pre-flight reflex without requiring the user to remember commands.
metadata:
  version: 4.1.0
---

# Omni-Kernel Orchestrator v4.1

The **Omni-Kernel Orchestrator** is an autonomous AI cognitive kernel and unified management engine for Antigravity. It unifies Skills, Inferred Rules, MCP Tool Drivers, Tri-Tier Omni-Memory, and Self-Bootstrapping Skill Synthesis with 0 static token overhead.

---

## Core Capabilities & Architecture

1. **Tri-Tier Cognitive Hierarchy (Omni-Memory v4.1)**:
   - **Tier 1 (L1 Reflex, <0.3ms reflex, <25ms subprocess turnaround)**: Ephemeral PreInvocation lifecycle hook in `hook_runner.py` with 100% Python stdlib. Clamps input to 2,048 chars, suppresses fillers, queries cached traces in <0.02ms, stages telemetry to `l1_staging_log`.
   - **Tier 2 (L2 Hybrid Memory, <15ms retrieval)**: Local embedded SQLite (`omni_memory.db`) with WAL mode (`PRAGMA synchronous = NORMAL;`, `busy_timeout = 5000;`). Employs Dual-Column FTS5 BM25 search (`content_exact` 10.0 vs `content_folded` 1.0) paired with Host CPU ONNX embeddings (`intfloat/multilingual-e5-small` INT8) and Reciprocal Rank Fusion ($k=20$).
   - **Tier 3 (L3 Background Consolidator)**: Out-of-band consolidation daemon in `consolidator.py`. Promotes multi-hit patterns ($\ge 2$ successes) with automated bilingual tags, applies bounded Ebbinghaus stability decay, soft-archives stale records (`status = 'Archived'`), and versions invariant rules (`status = 'Superseded'`).
2. **Autonomous Stack & Marker Detection**: Automatically inspects workspace marker files (`package.json`, `Cargo.toml`, `go.mod`, `pubspec.yaml`, `pom.xml`, `requirements.txt`, `pyproject.toml`, `Dockerfile`, `*.prisma`, `index.html`, etc.) to determine active tech stacks.
3. **Unified Resource Retrieval**: Matches user intent and stack markers against skills, domain rules, and MCP tool drivers in under 2ms.
4. **Cognitive Pre-Flight Assessment**: Implements the 4-axis deliberation matrix (**Lợi - Hại - Đủ - Thiếu**) before generating any code.
5. **Omni-Auditor Council Gate & Hard Gatekeeper**: Enforces strict architectural review via independent critic model (DeepSeek-V4.1-Flash) to eliminate echo chambers and blind spots before executing SDD task implementation.
6. **Worker Fleet Protocol**:
   - `local_worker_mi50` (AMD Instinct MI50 16GB HBM2 @ 1024 GB/s): Dedicated to SQLite WAL data access, IPC mutex locking, in-place `fast_edit`, and hardware telemetry.
   - `groq_worker_cloud` (Groq LPU @ 300-800+ tok/s): Dedicated to pure algorithmic calculations, string parsing, tokenization, and rapid unit test generation.
   - `gemini_worker_cloud` (Google Gemini 3.5 Flash-Lite / 3.8 Flash / 4 Argon): Dedicated to large-context codebase synthesis (>32K context), cross-module refactoring with 1M tokens context, multimodal vision (UI/diagrams), and deep mathematical/reasoning solutions via 10$/month API credits.

---

## Operational Workflow

When the user asks to implement, debug, test, or review code in any project:
1. **Mandatory Step 0: Resolve Unified Resources**:
   ```powershell
   python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --intent "<user_query>" --workspace "<current_workspace>"
   ```
2. **Cognitive Deliberation (Step 0.5)**:
   - Review the inferred rules and MCP tool suggestions.
   - Enforce Kernel Ring 0 Invariants (Zero-Trust Security, Data Safety, Ponytail Simplicity).
3. **Load and Execute**:
   - `read_file` the top candidate's `SKILL.md`.
   - Implement the smallest complete working diff (YAGNI).
4. **Synthesize Missing Capabilities (If Needed)**:
   ```powershell
   python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/synthesizer.py" --name "<name>" --desc "<desc>" --test "<test_code>"
   ```
5. **Reinforce and Evolve**:
   ```powershell
   python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --intent "<user_query>" --workspace "<current_workspace>" --feedback "<chosen_skill>"
   ```

---

## Self-Learning & Memory Management

- **View Learning Statistics**:
  ```powershell
  python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --learn-stats
  ```
- **Reset Learned Affinities**:
  ```powershell
  python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --reset-learning
  ```

---

## Re-Indexing & Kernel Skill Synchronization

Whenever you install new plugins, add new skills, or upgrade Omni-Kernel versions:
Run:
```powershell
python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/updater.py" --sync-kernel
```
or directly:
```powershell
python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/indexer.py"
```
The indexer will scan all sources and update the registry in ~150ms.
