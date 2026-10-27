---
name: omni-skill-orchestrator
description: >-
  Universal AI Skill & Plugin Intelligence: Automatically discovers, resolves, and auto-activates the optimal skill or agent for any project or task across 550+ (and up to 7,749+) installed plugins, active skills, library skills, and builtin tools without requiring the user to remember commands.
metadata:
  version: 1.0.0
---

# Omni-Skill Orchestrator

The **Omni-Skill Orchestrator** is an autonomous skill activation and management engine for Antigravity. It eliminates the need for users to remember skill names, slash commands, or manage active skills manually.

## Core Capabilities

1. **Autonomous Stack & Marker Detection**: Automatically inspects the current workspace for marker files (`package.json`, `Cargo.toml`, `go.mod`, `pubspec.yaml`, `pom.xml`, `requirements.txt`, `pyproject.toml`, `Dockerfile`, `*.prisma`, etc.) to determine active tech stacks.
2. **Intent-Based Progressive Retrieval**: Matches user prompt intent (in both English and Vietnamese) against the unified inverted index (`registry.json`) in under 5ms.
3. **Just-In-Time (JIT) Loading**: When an optimal skill is identified, the agent immediately reads its `SKILL.md` using `read_file` and executes following its documented patterns.
4. **Intelligent Arbitration**: If multiple skills overlap, the engine automatically selects the newer, higher-specificity, or project-local version (via the `skill-arbiter` protocol).

## Operational Workflow

When the user asks to implement, debug, test, or review code in any project:
1. **Never ask the user** to remember, enable, or type a skill name or command.
2. **Resolve the optimal skill**:
   - Check if a matching specialized skill exists in the system registry (`scripts/registry.json`).
   - If needed, run the resolver:
     ```powershell
     python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --intent "<user_query>" --workspace "<current_workspace>"
     ```
3. **Load and Execute**:
   - Use `read_file` to read the target `SKILL.md`.
   - Adhere strictly to the best practices, test requirements, and security rules of the loaded skill.
   - Combine with **Ponytail** (`lazy senior dev mode`) to produce the cleanest, shortest diff that completely solves the problem.

## Re-Indexing New Skills

Whenever you install new plugins or drop new skills into `~/.gemini/config/skills/` or `skills_library/`:
Run:
```powershell
python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/indexer.py"
```
The indexer will scan all sources and update the registry in ~150ms.
