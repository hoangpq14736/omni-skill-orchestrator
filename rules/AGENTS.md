# Omni-Kernel v3.0 Autonomous Protocol

You have access to the **Omni-Kernel v3.0 Orchestrator**, a unified autonomous intelligence engine governing Skills, Inferred Rules, MCP Tool Drivers, and Self-Evolution across 550+ capabilities.

## Operating Guidelines

1. **Kernel Ring 0 Invariants (Immutable)**:
   - **Zero-Trust Security:** Never hardcode secrets. Always validate and sanitize inputs at trust boundaries.
   - **Reliable Engineering:** Never silently swallow exceptions. Fail loudly with diagnostic context. Immutability first.
   - **Ponytail Simplicity:** Smallest complete working diff wins. YAGNI. Codebase helper > Standard library > Dependency > New code.

2. **Mandatory Step 0 Gatekeeper & Cognitive Pre-Flight Loop**:
   - BEFORE planning or modifying code on any technical task:
     Execute: `python "C:/Users/vuhuu/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --intent "<user_query>" --workspace "<current_workspace>"`
   - Use `read_file` to read the top candidate's `SKILL.md` before generating code.
   - Assess the 4 Cognitive Axes: **Lợi (Value)**, **Hại (Risks)**, **Đủ (Completeness)**, **Thiếu (Implicit Inferred Requirements)**.

3. **Autonomous Skill & Tool Synthesis (Self-Bootstrapping)**:
   - When a required domain or skill is missing from the 500+ library:
     Synthesize and validate in sandbox:
     `python "C:/Users/vuhuu/.gemini/config/plugins/omni-skill-orchestrator/scripts/synthesizer.py" --name "<name>" --desc "<desc>" --domain "<domain>" --test "<test_code>"`
   - Omni automatically reindexes the library in <150ms.

4. **Continuous Meta-Learning & Feedback Loop**:
   - When an alternative skill is selected or corrected:
     `python "C:/Users/vuhuu/.gemini/config/plugins/omni-skill-orchestrator/scripts/resolver.py" --intent "<user_query>" --workspace "<current_workspace>" --feedback "<chosen_skill>"`
   - Omni dynamically adapts learned affinities (`learned_affinities.json`).
