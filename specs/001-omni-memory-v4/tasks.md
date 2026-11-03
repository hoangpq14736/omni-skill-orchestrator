---
description: "Granular, dependency-ordered task breakdown for Omni-Memory v4.0 production upgrade"
---

# Tasks: Omni-Memory v4.0 Production Upgrade

**Input**: Design documents from `specs/001-omni-memory-v4/` (`spec.md`, `plan.md`) and ratified `docs/rfcs/RFC-004-omni-memory-v4.md`  
**Prerequisites**: `spec.md`, `plan.md`, `.specify/constitution.md`  
**Tests Included**: Yes (Executable Pytest suites in `specs/001-omni-memory-v4/tests/`)  

## Format: `- [ ] [TaskID] [P?] [Story?] Description with exact file path`
- `[TaskID]`: Unique sequential execution identifier (`T001`, `T002`, ...).
- `[P]`: Flag indicating the task can execute concurrently in parallel (isolated files).
- `[Story]`: User story tag (`[US1]`, `[US2]`, `[US3]`). Omitted for Setup, Foundational, and Polish phases.
- Exact file paths are included in all task descriptions.

---

## AI Worker Fleet Capability Allocation

| Worker Agent | Specialization & Tool Driver | Assigned Task Range | Rationale |
|---|---|---|---|
| **`local_worker_mi50`** | Tactical Python code generation, AST parsing, SQLite DDL, math algorithms, in-place surgical edits (`fast_edit`, `execute_code_task`, `generate_tests`) on local AMD Instinct MI50 GPU. | **T004 - T015, T017 - T022, T024 - T029** | Zero token cost, rapid in-place local file modifications, exact standard library compliance. |
| **`groq_worker_cloud`** | High-throughput architectural reasoning, cross-artifact consistency (`analyze`), synthetic test scenario generation, complex refactorings (`groq_code_gen`, `groq_fast_edit`, `groq_generate_tests`) on Groq LPU cluster. | **T001 - T003, T016, T023, T030 - T034** | High throughput for large scaffolding files, cross-tier integration suites, and multi-artifact convergence audits. |

---

## Phase 1: Setup & Scaffolding (Shared Infrastructure)

**Purpose**: Establish workspace directories, configuration, and shared test harnesses.

- [ ] T001 Initialize SDD feature directory and configuration files in `.specify/` and `specs/001-omni-memory-v4/`
- [ ] T002 [P] Configure shared Pytest fixtures and mock worker drivers in `specs/001-omni-memory-v4/tests/conftest.py`
- [ ] T003 [P] Configure Windows AppLocker and Python 3.11+ stdlib validation checks in `specs/001-omni-memory-v4/tests/test_environment.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure and defensive boundaries that MUST be complete before ANY user story can be implemented.

**⚠️ CRITICAL**: No user story implementation work can begin until this phase is complete and verified.

- [x] T004 Setup SQLite schema DDL (5 core tables + dual-column FTS5 virtual table + staging log + triggers + indexes) in `scripts/memory_schema.py`
- [x] T005 [P] Implement Vietnamese diacritic folding `fold_vietnamese(text)` (`đ/Đ` -> `d/D` + NFD strip) in `scripts/memory_utils.py`
- [x] T006 [P] Implement defensive FTS5 query sanitization pipeline `sanitize_fts5_query(query, fold=False)` in `scripts/memory_utils.py`
- [x] T007 [P] Implement Zero-Trust automated credential redaction regex filter in `scripts/sanitizer.py`
- [x] T008 Implement inter-process autostart file mutex lock (`llama_autostart.lock`) with 30s stale-lock recovery and 25s socket polling in `scripts/backend_client.py`

**Checkpoint**: Foundational libraries verified — User story implementations can now proceed in dependency order.

---

## Phase 3: User Story 1 - Sub-Millisecond L1 Reflex Grounding & Active Trace Cache (Priority: P1) 🎯 MVP

**Goal**: Deliver synchronous pre-flight lifecycle hook executing in $<25\text{ ms}$ (P99 total OS subprocess budget, $<0.30\text{ ms}$ internal reflex) that injects active hardware fleet directives and recalls verified procedural fixes using 100% Python Standard Library.

**Independent Test**: Execute `pytest specs/001-omni-memory-v4/tests/test_tier1_reflex.py`; verify P99 internal latency $<0.30\text{ ms}$, 2,048-char head clamping on 100 KB inputs, filler phrase suppression in $<1.0\text{ ms}$, and active worker directives formatted correctly.

### Tests for User Story 1 (Write & verify first) ⚠️
- [x] T009 [P] [US1] Author executable Pytest test suite for Tier 1 reflex hook, latency benchmark, 2,048-char head clamp, and filler suppression in `specs/001-omni-memory-v4/tests/test_tier1_reflex.py`

### Implementation for User Story 1
- [x] T010 [US1] Implement 2,048-character head clamping invariant ($\text{prompt}[:2048]$) in `scripts/hook_runner.py`
- [x] T011 [US1] Implement conversational filler phrase suppression (<1.0ms fast-exit with full-sentence boundary matching) in `scripts/hook_runner.py`
- [x] T012 [US1] Implement MTime-validated in-memory inverted index loader for `proven_traces.json` in `scripts/experiential_memory.py`
- [x] T013 [US1] Format and inject dynamic system grounding context for `local_worker_mi50` and `groq_worker_cloud` in `scripts/hook_runner.py`
- [x] T014 [US1] Decouple synchronous file writes from pre-flight execution path into `l1_staging_log` table with `PRAGMA synchronous = NORMAL;` preserving 100% stdlib in `scripts/hook_runner.py`
- [x] T015 [US1] Run benchmark validation to confirm Tier 1 P99 internal execution latency $<0.30\text{ ms}$ in `specs/001-omni-memory-v4/tests/test_tier1_reflex.py`

**Checkpoint**: User Story 1 (MVP) is fully functional, independently verified, and satisfies all P1 requirements.

---

## Phase 4: User Story 2 - Local Hybrid Semantic & Episodic Memory (Priority: P2)

**Goal**: Deliver local embedded SQLite 3 database (`omni_memory.db`) with dual-column FTS5 BM25 search, host CPU ONNX dense vector embeddings via `intfloat/multilingual-e5-small` (Topology A with asymmetric prefixes), and Reciprocal Rank Fusion ($k=20$) executing in $<15\text{ ms}$.

**Independent Test**: Execute `pytest specs/001-omni-memory-v4/tests/test_tier2_hybrid_memory.py`; verify WAL mode, schema integrity, dual-column `fold_vietnamese`, FTS5 operator escaping, IEEE-754 vector cosine similarity, RRF $k=20$ monotonicity, and offline vector fallback.

### Tests for User Story 2 (Write & verify first) ⚠️
- [x] T016 [P] [US2] Author executable Pytest test suite for Tier 2 SQLite schemas, dual-column FTS5, syntax sanitization, vector cosine similarity, RRF $k=20$, and pure FTS5 offline fallback in `specs/001-omni-memory-v4/tests/test_tier2_hybrid_memory.py`

### Implementation for User Story 2
- [x] T017 [US2] Implement SQLite 3 Single-Writer Queue pattern (`queue.Queue` dedicated thread, `BEGIN IMMEDIATE`, `busy_timeout=5000`, `wal_autocheckpoint=1000`) in `scripts/memory_engine.py`
- [x] T018 [US2] Implement Topology A Host CPU ONNX embedding generator (`intfloat/multilingual-e5-small` INT8) with mandatory `"passage: "` and `"query: "` prefixes in `scripts/embedding_service.py`
- [x] T019 [US2] Implement IEEE-754 float32 vector BLOB serialization and pre-normalized cosine similarity evaluator in `scripts/memory_engine.py`
- [x] T020 [US2] Implement Reciprocal Rank Fusion algorithm ($k=20$) combining BM25 and dense vector rankings in `scripts/memory_engine.py`
- [x] T021 [US2] Implement dual-column FTS5 search (`bm25(episodic_fts, 10.0, 1.0) ORDER BY rank_score ASC`) with canonical `workspace_hash` (`os.path.normcase`) in `scripts/memory_engine.py`
- [x] T022 [US2] Implement automatic fallback to pure FTS5 BM25 lexical search when embedding engine is offline in `scripts/memory_engine.py`

**Checkpoint**: User Story 2 is fully functional; hybrid search retrieves semantic and episodic records in $<15\text{ ms}$.

---

## Phase 5: User Story 3 - Asynchronous Background Consolidation & Memory Telemetry (Priority: P3)

**Goal**: Deliver out-of-band consolidation daemon (`scripts/consolidator.py`) clustering activation logs, promoting multi-hit patterns with automated bilingual tags, managing soft-archiving via bounded Ebbinghaus decay, and versioning invariants.

**Independent Test**: Execute `pytest specs/001-omni-memory-v4/tests/test_tier3_consolidation.py`; verify batch ingestion idempotency, pattern promotion with bilingual tags, Ebbinghaus decay $S(t) \in [0.0, 1.0]$ in day units, 7-day grace period, soft-archiving, and permanent invariant versioning.

### Tests for User Story 3 (Write & verify first) ⚠️
- [x] T023 [P] [US3] Author executable Pytest test suite for Tier 3 batch ingestion, pattern clustering, bilingual tag extraction, Ebbinghaus decay, soft-archiving, and invariant versioning in `specs/001-omni-memory-v4/tests/test_tier3_consolidation.py`

### Implementation for User Story 3
- [x] T024 [US3] Implement batch ingestion of `l1_staging_log` events (chunks of 100) into `activation_events` via Single-Writer in `scripts/consolidator.py`
- [x] T025 [US3] Implement intent clustering and frequency promotion for multi-hit patterns ($\ge 2$ successes) in `scripts/consolidator.py`
- [x] T026 [US3] Implement automated English/Vietnamese `bilingual_tags` keyword extraction during trace promotion in `scripts/consolidator.py`
- [x] T027 [US3] Implement bounded Ebbinghaus decay $S(t) = S_0 \cdot \exp\left(-\frac{\lambda_0 \Delta t}{1 + \alpha \ln(1 + N_{\text{hits}})}\right)$ with $\Delta t$ in days from `last_accessed_at` in `scripts/consolidator.py`
- [x] T028 [US3] Implement soft-archiving (`status = 'Archived'`) for $S(t) < 0.20$ ($\Delta t \ge 7\text{d}$) and invariant rule versioning (`status = 'Superseded'`, `superseded_by`) in `scripts/consolidator.py`
- [x] T029 [US3] Implement incremental WAL vacuuming (`PRAGMA incremental_vacuum(100);`) and atomic snapshot writing in `scripts/consolidator.py`

**Checkpoint**: All three user stories are complete, independently functional, and verified by passing test suites.

---

## Phase 6: Polish, Integration & Cross-Cutting Hardening

**Purpose**: End-to-end integration, migration tooling, security audit, and documentation updates across the repository.

- [x] T030 Execute full integration and performance regression suite across all tiers in `specs/001-omni-memory-v4/tests/`
- [x] T031 [P] Author one-time idempotent migration script migrating flat-file data into SQLite in `scripts/migrate_v3_to_v4.py`
- [x] T032 Verify Zero-Trust credential sanitization and confirm zero cloud data leakage across all storage paths in `specs/001-omni-memory-v4/tests/test_omni_memory_e2e_security.py`
- [x] T033 Enshrine Rule 6 Omni-Memory v4.0 Tri-Tier Cognitive Protocol and Worker Fleet Directives in `rules/AGENTS.md`
- [x] T034 Run GitHub Spec Kit cross-artifact convergence audit (`analyze`) to confirm 100% spec-to-code alignment

---

## Dependencies & Execution Order

### Phase Dependencies
1. **Setup (Phase 1)**: Can start immediately; no dependencies.
2. **Foundational (Phase 2)**: Depends on Phase 1; **BLOCKS** all user story implementations.
3. **User Story 1 (Phase 3 - P1)**: Depends on Phase 2; can execute in parallel with or prior to US2/US3.
4. **User Story 2 (Phase 4 - P2)**: Depends on Phase 2; can execute in parallel with US1/US3.
5. **User Story 3 (Phase 5 - P3)**: Depends on Phase 2; integrates with US1 cache and US2 SQLite database.
6. **Polish (Phase 6)**: Depends on completion of all user story phases (P1, P2, P3).

### Within Each User Story
- Pytest test suites MUST be authored first and verified before runtime code modification.
- Data structures and utility functions before service integration.
- Performance benchmarks run to confirm SLA adherence before marking story complete.
