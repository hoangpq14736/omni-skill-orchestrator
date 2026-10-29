---
name: omni-skill-orchestrator
description: >-
  Universal AI Skill & Plugin Intelligence: Automatically discovers, resolves, and auto-activates the optimal skill or agent for any project or task across 550+ (and up to 7,749+) installed plugins, active skills, library skills, and builtin tools without requiring the user to remember commands.
metadata:
  version: 2.0.0
---

# Omni-Kernel Orchestrator v2.0

The **Omni-Kernel Orchestrator** is an autonomous AI cognitive kernel and unified management engine for Antigravity. It unifies Skills, Inferred Rules, MCP Tool Drivers, and Self-Bootstrapping Skill Synthesis with 0 static token overhead.

## Core Capabilities

1. **Autonomous Stack & Marker Detection**: Automatically inspects workspace marker files (`package.json`, `Cargo.toml`, `go.mod`, `pubspec.yaml`, `pom.xml`, `requirements.txt`, `pyproject.toml`, `Dockerfile`, `*.prisma`, `index.html`, etc.) to determine active tech stacks.
2. **Unified Resource Retrieval**: Matches user intent and stack markers against skills, domain rules, and MCP tool drivers in under 2ms.
3. **Cognitive Pre-Flight Assessment**: Implements the 4-axis deliberation matrix (**Lợi - Hại - Đủ - Thiếu**) before generating any code.
4. **Autonomous Skill & Tool Synthesis**: Hypothesizes, authors, sandbox-tests, and auto-promotes new skills and tools when encountering novel problems.
5. **Continuous Meta-Learning**: Adapts token-skill affinities dynamically via `--feedback <skill>`.

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

## Self-Learning & Memory Management

- **View Learning Statistics**:
  ```powershell
  python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --learn-stats
  ```
- **Reset Learned Affinities**:
  ```powershell
  python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --reset-learning
  ```

## Re-Indexing New Skills

Whenever you install new plugins or drop new skills into `~/.gemini/config/skills/` or `skills_library/`:
Run:
```powershell
python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/indexer.py"
```
The indexer will scan all sources and update the registry in ~150ms.
