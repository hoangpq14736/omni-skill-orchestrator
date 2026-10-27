# Omni-Skill Autonomous Protocol

You have access to the **Omni-Skill Orchestrator**, a unified management, auto-activation, and self-learning engine governing 550+ (and up to 7,749+) skills across all installed plugins, active skills, offline libraries, and builtin tools.

## Mandatory Operating Guidelines

1. **Zero-Memory Autonomous Operation**:
   - **NEVER** ask or expect the user to remember, activate, or name skills or slash commands manually.
   - Automatically detect the current workspace tech stack (marker files: `package.json`, `Cargo.toml`, `go.mod`, `pubspec.yaml`, `pom.xml`, `requirements.txt`, `pyproject.toml`, `Dockerfile`, `schema.prisma`, `index.html`, etc.).
   - Automatically identify the user's intent from their prompt (supports both English and Vietnamese technical keywords).

2. **Mandatory Step 0 Gatekeeper (Zero-Skip Dynamic Activation)**:
   - BEFORE planning, writing, or refactoring code for any technical task, you MUST run the resolver:
     `python "C:/Users/vuhuu/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --intent "<user_query>" --workspace "<current_workspace>"`
   - Use `read_file` to read the top candidate's `SKILL.md` from its resolved path before generating code.
   - Never skip resolution assuming internal model knowledge is sufficient.

3. **Autonomous Meta-Learning & Feedback Loop**:
   - When a skill other than rank #1 is selected or corrected by the user, register feedback immediately:
     `python "C:/Users/vuhuu/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --intent "<user_query>" --workspace "<current_workspace>" --feedback "<chosen_skill>"`
   - Omni dynamically reinforces learned affinities (`learned_affinities.json`) to continuously evolve accuracy across future sessions.

4. **Intelligent Arbitration (Newer & Better Wins)**:
   - When multiple skills cover the same domain, always adhere to the **Skill Arbiter Protocol**:
     - Modern / newer version overrides older versions.
     - Specific framework skill overrides generic language skill.
     - Workspace-local skill overrides system defaults.
   - Follow Ponytail principles: prioritize minimal diffs, YAGNI, standard library first, and eliminate redundant abstractions.
