---
name: omni-skill-orchestrator
description: >-
  Universal AI Skill & Plugin Intelligence: Automatically discovers, resolves, and auto-activates the optimal skill or agent for any project or task across 550+ (and up to 7,749+) installed plugins, active skills, library skills, and builtin tools without requiring the user to remember commands.
metadata:
  version: 1.1.0
---

# Omni-Skill Orchestrator

The **Omni-Skill Orchestrator** is an autonomous skill activation, self-learning, and management engine for Antigravity. It eliminates the need for users to remember skill names, slash commands, or manage active skills manually.

## Core Capabilities

1. **Autonomous Stack & Marker Detection**: Automatically inspects the current workspace for marker files (`package.json`, `Cargo.toml`, `go.mod`, `pubspec.yaml`, `pom.xml`, `requirements.txt`, `pyproject.toml`, `Dockerfile`, `*.prisma`, `index.html`, etc.) to determine active tech stacks.
2. **Intent-Based Progressive Retrieval**: Matches user prompt intent (in both English and Vietnamese) against the unified inverted index (`registry.json`) in under 5ms.
3. **Mandatory Step 0 Gatekeeper (Zero-Skip Activation)**: Enforces proactive skill discovery before code generation so agents never guess or rely on stale training memory.
4. **Intelligent Arbitration**: If multiple skills overlap, the engine automatically selects the newer, higher-specificity, or project-local version (via the `skill-arbiter` protocol).
5. **Autonomous Meta-Learning (Self-Evolution)**: Learns from agent and user feedback (`--feedback <skill>`), dynamically adjusting token-skill affinities in `learned_affinities.json` to continuously improve ranking accuracy.

## Operational Workflow

When the user asks to implement, debug, test, or review code in any project:
1. **Never ask the user** to remember, enable, or type a skill name or command.
2. **Mandatory Step 0: Resolve the optimal skill**:
   - Run the resolver before writing code:
     ```powershell
     python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --intent "<user_query>" --workspace "<current_workspace>"
     ```
3. **Load and Execute**:
   - Use `read_file` to read the top candidate's `SKILL.md`.
   - Adhere strictly to the best practices, test requirements, and security rules of the loaded skill.
   - Combine with **Ponytail** (`lazy senior dev mode`) to produce the cleanest, shortest diff that completely solves the problem.
4. **Reinforce and Evolve**:
   - If the user or agent chooses an alternative skill, log the reinforcement:
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
