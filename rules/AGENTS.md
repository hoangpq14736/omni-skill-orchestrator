# Omni-Skill Autonomous Protocol

You have access to the **Omni-Skill Orchestrator**, a unified management and auto-activation engine governing 550+ (and up to 7,749+) skills across all installed plugins, active skills, offline libraries, and builtin tools.

## Mandatory Operating Guidelines

1. **Zero-Memory Autonomous Operation**:
   - **NEVER** ask or expect the user to remember, activate, or name skills or slash commands manually.
   - Automatically detect the current workspace tech stack (marker files: `package.json`, `Cargo.toml`, `go.mod`, `pubspec.yaml`, `pom.xml`, `requirements.txt`, `pyproject.toml`, `Dockerfile`, `schema.prisma`, etc.).
   - Automatically identify the user's intent from their prompt (supports both English and Vietnamese technical keywords).

2. **Just-In-Time (JIT) Skill Activation**:
   - Before writing or refactoring code for any non-trivial task, use `read_file` to read the corresponding `SKILL.md` from:
     - Plugin skills: `~/.gemini/config/plugins/<plugin>/skills/<skill>/SKILL.md`
     - Active skills: `~/.gemini/config/skills/<skill>/SKILL.md`
     - Offline library: `~/.gemini/config/skills_library/<skill>/SKILL.md`
   - If unsure which skill is optimal among multiple candidates, query the resolver:
     `python "~/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --intent "<user_query>" --workspace "<current_workspace>"`

3. **Intelligent Arbitration (Newer & Better Wins)**:
   - When multiple skills cover the same domain, always adhere to the **Skill Arbiter Protocol**:
     - Modern / newer version overrides older versions.
     - Specific framework skill overrides generic language skill.
     - Workspace-local skill overrides system defaults.
   - Follow Ponytail principles: prioritize minimal diffs, YAGNI, standard library first, and eliminate redundant abstractions.
