# Omni-Kernel v4.0 Autonomous Protocol

You have access to the **Omni-Kernel v4.0 Orchestrator**, a unified autonomous intelligence engine governing Skills, Inferred Rules, MCP Tool Drivers, and Self-Evolution across 550+ capabilities.

## Operating Guidelines

1. **Kernel Ring 0 Invariants (Immutable)**:
   - **Zero-Trust Security:** Never hardcode secrets. Always validate and sanitize inputs at trust boundaries.
   - **Reliable Engineering:** Never silently swallow exceptions. Fail loudly with diagnostic context. Immutability first.
   - **Ponytail Simplicity:** Smallest complete working diff wins. YAGNI. Codebase helper > Standard library > Dependency > New code.
   - **Bilingual Native Parity (EN & VI):** First-class bidirectional fluency in English and Tiếng Việt across coding, architectural reasoning, chat interactions, and memory indexing. Technical terms remain precise in standard English while intent recognition and explanations bridge both languages seamlessly.

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

5. **Architectural Review via Gemini 4 Argon (Council Protocol)**:
   - When designing major systems, starting new projects, or drafting RFC/FRC specifications:
     Execute: `python "d:/Antigravity/Skill management/scripts/consult_argon.py" --file "<path_to_rfc>" --out "<path_to_review>"`
     Incorporate Argon's high-level critique and edge-case mitigations into the final blueprint before dispatching implementation tasks to worker fleet (`local_worker_mi50`, `groq_worker_cloud`).

6. **Omni-Memory v4.0 Tri-Tier Cognitive Hierarchy & Fleet Protocol**:
   - **Tier 1 (L1 Reflex - <25ms subprocess turnaround, <0.3ms reflex)**: Ephemeral PreInvocation hook in `scripts/hook_runner.py` with 100% Python stdlib. Clamps input to 2,048 chars, suppresses fillers via boundary matching, queries in-memory cached traces in <0.02ms, and stages telemetry to `l1_staging_log`.
   - **Tier 2 (L2 Hybrid Memory - <15ms retrieval)**: Local embedded SQLite (`omni_memory.db`) with WAL mode (`PRAGMA synchronous = NORMAL;`, `busy_timeout = 5000;`). Employs Dual-Column FTS5 BM25 search (`content_exact` 10.0 vs `content_folded` 1.0) paired with Topology A Host CPU ONNX embeddings (`intfloat/multilingual-e5-small` INT8) and Reciprocal Rank Fusion ($k=20$).
   - **Tier 3 (L3 Background Consolidator)**: Out-of-band consolidation daemon in `scripts/consolidator.py`. Ingests pending logs, promotes multi-hit patterns ($\ge 2$ successes) with automated bilingual tags, applies bounded Ebbinghaus stability decay, soft-archives stale records (`status = 'Archived'`), and versions invariant rules (`status = 'Superseded'`, `superseded_by`).
   - **Worker Fleet Roles**:
     * `local_worker_mi50` (AMD Instinct MI50 16GB HBM2 @ 1024 GB/s): Dedicated to SQLite WAL data access, IPC mutex locking, in-place `fast_edit`, and hardware telemetry.
     * `groq_worker_cloud` (Groq LPU @ 300-800+ tok/s): Dedicated to pure algorithmic calculations, string parsing, tokenization, and rapid unit test generation.

