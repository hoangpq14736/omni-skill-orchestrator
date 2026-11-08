---
description: "Granular, dependency-ordered task breakdown for Omni-Graph (Graphify) Codebase Topology Engine"
---

# Tasks: Omni-Graph (Graphify) Codebase Topology Engine

**Input Documents**: Design documents from `specs/003-omni-graph/` (`spec.md`, `plan.md`), codebase survey `survey_codebase.md`, incident forensic analysis `survey_constitution_incidents.md`, technical domain survey `survey_graphify_capabilities.md`, and Architectural Directive on Autonomous Zero-Config Bootstrapping.  
**Prerequisites**: `spec.md`, `plan.md`, `.specify/constitution.md` (v4.1.0).  
**Tests Included**: Yes (Executable Pytest test suites in `specs/003-omni-graph/tests/`).  

## Format: `- [ ] [TaskID] [P?] [Story?] Description with exact file path`
- `[TaskID]`: Unique sequential execution identifier (`T001` through `T045`).
- `[P]`: Flag indicating the task can execute concurrently in parallel (isolated files/modules).
- `[Story]`: User story tag (`[US1]` Signature Contract Guard, `[US2]` Lifecycle Registration Guard, `[US3]` Blast Radius Traversal & Visualization, `[US4]` Autonomous Bootstrapping & Kernel Integration). Omitted for Setup and Foundational phases.
- Exact file paths are specified in all task descriptions.

---

## AI Worker Fleet Capability Allocation

| Worker Agent | Specialization & Tool Driver | Assigned Task Range | Architectural Rationale |
|---|---|---|---|
| **`local_worker_mi50`** | Tactical Python code generation, AST visitor implementation, SQLite DDL & WAL tuning, recursive CTE queries, in-place surgical edits (`fast_edit`, `execute_code_task`), post-edit self-healing hooks, and offline test execution on local AMD Instinct MI50 GPU (16GB HBM2 @ 1024 GB/s). | **T005 - T013, T016 - T023, T026 - T032, T035 - T040** | 100% offline security, zero token consumption, sub-millisecond local disk edits, exact standard library compliance, and direct SQLite file I/O operations. |
| **`groq_worker_cloud`** | Ultra-high-throughput code synthesis (300–800+ tok/s), JSON/schema boilerplate generation, massive Pytest suite authoring (`groq_generate_tests`, `groq_code_gen`), standalone HTML5 Canvas visualizer synthesis, Git hygiene hooks, and cross-artifact convergence audits (`analyze`) on Groq LPU cluster. | **T001 - T004, T014 - T015, T024 - T025, T033 - T034, T041 - T045** | Near-zero latency for large scaffolding files, comprehensive edge-case test matrices, rapid regex lexer synthesis, and multi-file convergence verification. |

---

## Milestone M1: Storage & AST Extraction Core (Tasks T001 - T015)

### Phase 1: Setup & Scaffolding (Shared Infrastructure)
**Purpose**: Establish workspace directories, configuration, test fixtures, and shared mock harnesses.

- [ ] T001 Initialize feature test directory and configuration files in `specs/003-omni-graph/tests/__init__.py` and `specs/003-omni-graph/tests/conftest.py`
- [ ] T002 [P] Configure shared Pytest fixtures, temporary repository tree generator, and AST test vectors in `specs/003-omni-graph/tests/conftest.py`
- [ ] T003 [P] Create synthetic flawed codebase fixtures reproducing parameter drift, missing kwargs, dangling Discord commands, and circular imports in `specs/003-omni-graph/tests/fixtures/synthetic_repo/`
- [ ] T004 [P] Configure Windows AppLocker compliance and Python 3.11+ stdlib validation checks in `specs/003-omni-graph/tests/test_environment.py`

### Phase 2: Core Storage, Git Hygiene & Autonomous Bootstrapping (Blocking Prerequisites)
**Purpose**: Establish dedicated SQLite WAL storage engine, automated Git hygiene, and autonomous zero-config cold-start discovery.

- [ ] T005 Implement dedicated SQLite WAL connection manager with strict PRAGMA configurations (`journal_mode = WAL`, `synchronous = NORMAL`, `busy_timeout = 5000`, `foreign_keys = ON`, `temp_store = MEMORY`) in `plugins/omni-skill-orchestrator/scripts/omni_graph/storage.py`
- [ ] T006 Implement complete relational schema DDL (`file_hashes`, `nodes`, `signatures`, `edges`, `lifecycle_hooks`) and covering B-Tree indexes (`idx_edges_tgt_rel`, `idx_edges_src_rel`, `idx_nodes_file`, `idx_signatures_file`) in `plugins/omni-skill-orchestrator/scripts/omni_graph/storage.py`
- [ ] T007 [P] Implement Git hygiene manager ensuring `<workspace>/.omni/` is automatically appended to `<workspace>/.gitignore` (with `# Omni-Kernel workspace artifacts` header) without duplicate entries in `plugins/omni-skill-orchestrator/scripts/omni_graph/git_hygiene.py`
- [ ] T008 Implement two-tier change detection pipeline (`os.stat` mtime/size pre-filter + SHA-256 content hash comparison) in `plugins/omni-skill-orchestrator/scripts/omni_graph/fingerprint.py`
- [ ] T009 Implement Autonomous Cold Start JIT Discovery engine detecting missing `<workspace>/.omni/codebase_graph.db` and executing initial AST sweep in $<100\text{ms}$ on first turn in `plugins/omni-skill-orchestrator/scripts/omni_graph/bootstrap.py`
- [ ] T010 Implement atomic transaction manager (`BEGIN IMMEDIATE`, file-scoped cascading delete and batch insert) in `plugins/omni-skill-orchestrator/scripts/omni_graph/storage.py`
- [ ] T011 Author unit test suite verifying SQLite WAL concurrency, transaction rollbacks, foreign key cascades, Git hygiene, and bootstrap cold start in `specs/003-omni-graph/tests/test_storage.py`

### Phase 3: AST Extraction Engine
**Purpose**: Extract syntax nodes, parameter signatures, call sites, and import mappings using 100% Python standard library `ast`.

- [ ] T012 Implement `ast.NodeVisitor` engine extracting modules, classes, functions, async functions, and methods with 1-indexed line ranges and docstrings in `plugins/omni-skill-orchestrator/scripts/omni_graph/ast_extractor.py`
- [ ] T013 Implement signature extractor mapping `ast.arguments` (posonlyargs, args, tail-aligned defaults count, vararg, kwonlyargs, kw_defaults booleans, kwarg) in `plugins/omni-skill-orchestrator/scripts/omni_graph/ast_extractor.py`
- [ ] T014 Implement call-site extractor (`ast.Call`) recording caller node ID, target identifier expression, positional argument count, keyword names list, splat booleans (`*args`, `**kwargs`), line numbers, and await context in `plugins/omni-skill-orchestrator/scripts/omni_graph/ast_extractor.py`
- [ ] T015 [P] Implement import resolution and scope table builder (`import x`, `from x import y as z`, relative imports `.` and `..`) in `plugins/omni-skill-orchestrator/scripts/omni_graph/ast_extractor.py`

**Milestone M1 Checkpoint**: Core storage, Git hygiene, autonomous cold-start sweep, and AST extraction verified; database populates deterministically from raw Python source files.

---

## Milestone M2: Contract & Registration Guards (Tasks T016 - T025)

### Phase 4: Signature Contract Guard (Priority: P1) 🎯 MVP
**Purpose**: Statically verify call sites against function definition signatures across module boundaries to prevent parameter mismatch exceptions.

- [ ] T016 [US1] Implement hardened `StaticSignature` model and static signature binding engine with `renamed_params` drift mapping, method receiver normalization (`self`/`cls` stripping on bound calls, decorator awareness), and unbound class call receiver compensation (`is_unbound_class_call`) in `plugins/omni-skill-orchestrator/scripts/omni_graph/contract_guard.py`
- [ ] T017 [US1] Implement static detection algorithms for the 8 contract failure modes (FAIL-01 through FAIL-08) incorporating the 4 hardened validator fixes: (1) `FAIL-07` drift differentiation via `renamed_params`, (2) unbound class call receiver compensation (`effective_pos_count = max(0, pos_count - 1)`), (3) PEP 570 positional-only args with `**kwargs` capture, and (4) single-violation emission (suppressing redundant `FAIL-02` when flagged as `FAIL-04`) in `plugins/omni-skill-orchestrator/scripts/omni_graph/contract_guard.py`
- [ ] T018 [US1] Implement cross-module symbol resolution mapping call expressions (`module.func`, `self.method`, aliased imports) to canonical node IDs in `plugins/omni-skill-orchestrator/scripts/omni_graph/contract_guard.py`
- [ ] T019 [US1] Implement diagnostic error formatter emitting line numbers, caller contexts, expected signatures, and suggested parameter names in `plugins/omni-skill-orchestrator/scripts/omni_graph/contract_guard.py`
- [ ] T020 [US1] Author exhaustive Pytest suite reproducing the SVBot incident (FAIL-03 `allocated_ram` vs `ram`), validating all 8 contract failure modes, and integrating the 16 adversarial test vectors from `tests/test_omni_graph_validator_empirical.py` in `specs/003-omni-graph/tests/test_contract_guard.py`

### Phase 5: Lifecycle Registration Guard (Priority: P2)
**Purpose**: Detect missing synchronization hooks, orphaned implementations, and dead dispatch references.

- [ ] T021 [US2] Implement declarative invariant rule parser supporting decorator validation, JSON/dict manifest verification, and dispatch integrity in `plugins/omni-skill-orchestrator/scripts/omni_graph/lifecycle_guard.py`
- [ ] T022 [US2] Implement orphan implementation detector (flagging entities defined with hook/plugin base classes or decorators but absent from registration tables) in `plugins/omni-skill-orchestrator/scripts/omni_graph/lifecycle_guard.py`
- [ ] T023 [US2] Implement dead dispatch reference detector (flagging registry entries or dispatch dictionaries pointing to deleted or renamed AST symbols) in `plugins/omni-skill-orchestrator/scripts/omni_graph/lifecycle_guard.py`
- [ ] T024 [P] [US2] Implement handler signature compatibility checker validating registered handler signatures against canonical hook contracts in `plugins/omni-skill-orchestrator/scripts/omni_graph/lifecycle_guard.py`
- [ ] T025 [P] [US2] Author Pytest suite reproducing dangling Discord slash commands (`@app_commands.command` without `tree.sync()`) and dead registry entries in `specs/003-omni-graph/tests/test_lifecycle_guard.py`

**Milestone M2 Checkpoint**: Signature and Lifecycle guards active; static analysis catches cross-module parameter errors and orphaned registrations prior to code execution.

---

## Milestone M3: Blast Radius Traversal & Visualization (Tasks T026 - T034)

### Phase 6: Recursive CTE Traversal Engine (Priority: P1)
**Purpose**: Deliver sub-millisecond transitive caller and callee impact graph traversals using SQLite native Recursive CTEs.

- [ ] T026 [US3] Implement transitive reverse caller traversal via SQLite `WITH RECURSIVE` CTE with depth clamping and shortest hop distance calculation in `plugins/omni-skill-orchestrator/scripts/omni_graph/traversal.py`
- [ ] T027 [US3] Implement delimiter-safe cycle traversal invariant using pipe token isolation (`'|' || id || '|'`) to prevent infinite loops and prefix collisions in `plugins/omni-skill-orchestrator/scripts/omni_graph/traversal.py`
- [ ] T028 [US3] Implement forward callee dependency tree query computing transitive downstream dependencies in `plugins/omni-skill-orchestrator/scripts/omni_graph/traversal.py`
- [ ] T029 [US3] Implement impact risk scoring algorithm (Tier 1: Direct Callers, Tier 2: Transitive Callers <3 hops, Tier 3: Cascading Ripple >3 hops) in `plugins/omni-skill-orchestrator/scripts/omni_graph/traversal.py`
- [ ] T030 [US3] Author unit and performance benchmark test suite validating sub-0.30ms query latency on 1,000-node graph fixtures in `specs/003-omni-graph/tests/test_traversal.py`

### Phase 7: Offline Visualization & Topology Reporting (Priority: P3)
**Purpose**: Provide intuitive, self-contained visual inspection and CI/CD markdown reports with zero external network dependencies.

- [ ] T031 [US3] Implement standalone HTML5 Canvas / force-simulation interactive visualizer generator (`graph.html`) with zero CDN and zero external dependencies in `plugins/omni-skill-orchestrator/scripts/omni_graph/visualizer.py`
- [ ] T032 [US3] Implement interactive visualizer features (pan/zoom, node search filter, blast radius illumination with upstream red/downstream cyan, inspector sidebar) in `plugins/omni-skill-orchestrator/scripts/omni_graph/visualizer.py`
- [ ] T033 [P] [US3] Implement structured Markdown topology report generator (`graph_report.md`) summarizing nodes, edges, contract failures, high-risk hubs, and cache hit rates in `plugins/omni-skill-orchestrator/scripts/omni_graph/reporter.py`
- [ ] T034 [P] [US3] Author verification test suite ensuring `graph.html` contains zero external network links (`http://`, `https://`, CDN scripts) and renders cleanly in standard browsers in `specs/003-omni-graph/tests/test_visualizer.py`

**Milestone M3 Checkpoint**: Sub-millisecond graph traversals verified; offline interactive topology visualization operational.

---

## Milestone M4: Integration, Hook Wiring & Zero-Regression Validation (Tasks T035 - T044)

### Phase 8: Unified CLI Driver (Priority: P2)
**Purpose**: Deliver self-contained developer and automation command-line interface.

- [ ] T035 [US4] Implement unified CLI driver `plugins/omni-skill-orchestrator/scripts/omni_graph.py` supporting `--scan`, `--rebuild`, `--check-signatures`, `--check-lifecycle`, `--blast-radius`, `--visualize`, `--report`, and `--bootstrap`
- [ ] T036 [US4] Implement graceful error handling, POSIX exit codes (0=clean, 1=violations found, 2=configuration/path error), and fail-closed diagnostics in `plugins/omni-skill-orchestrator/scripts/omni_graph.py`
- [ ] T037 Author CLI integration test suite verifying argument parsing, exit codes, and output artifacts in `specs/003-omni-graph/tests/test_cli.py`

### Phase 9: Pre-Flight Hook, Post-Edit Self-Healing & Resolver Integration (Priority: P2)
**Purpose**: Wire non-blocking graph advisories, pre-flight delta maintenance (<2ms), post-edit self-healing, and cognitive enrichment into Omni-Kernel runtime lifecycle while strictly preserving $<25\text{ms}$ hook turnaround SLA.

- [ ] T038 [US4] Implement pre-flight incremental delta maintenance check (<2ms) in `scripts/hook_runner.py` verifying file mtimes against `codebase_files_meta`
- [ ] T039 [US4] Implement non-blocking, fail-soft advisory reader in `scripts/hook_runner.py` querying `codebase_graph.db` with `busy_timeout=100ms` and preserving $<25\text{ms}$ hook turnaround SLA
- [ ] T040 [US4] Implement post-edit self-healing hook in `plugins/omni-skill-orchestrator/scripts/omni_graph/self_healing.py` executing micro-index update on modified files immediately upon tool edit completion
- [ ] T041 [US4] Implement Cognitive Pre-Flight Loop enrichment in `scripts/resolver.py` injecting blast radius caller lists into "Đủ (Completeness)" and signature risks into "Hại (Risks)"
- [ ] T042 [P] [US4] Author integration test suite verifying hook runner execution time remains $<25\text{ms}$, pre-flight delta check executes in $<2\text{ms}$, and self-healing hook updates database in $<15\text{ms}$ in `specs/003-omni-graph/tests/test_kernel_integration.py`

### Phase 10: Zero-Regression & Multi-Agent Verification (Priority: P1)
**Purpose**: Validate 100% backward compatibility across Omni-Memory v4.1, DeepSeek Auditor Council Gatekeeper, and complete all quality gates.

- [ ] T043 Execute regression test suite verifying Omni-Memory v4.1 (L1 reflex, L2 SQLite WAL hybrid memory, L3 consolidator daemon) operates with 100% backward compatibility in `tests/test_engine.py` and `tests/test_tier1_reflex.py`
- [ ] T044 Author and execute multi-process concurrency stress test verifying simultaneous Omni-Memory writes and Omni-Graph traversals with zero lock contention in `specs/003-omni-graph/tests/test_zero_conflict_concurrency.py`
- [ ] T045 Execute Stop-Point Zero-Regression verification suite on DeepSeek Auditor client (`pytest specs/002-deepseek-v41-auditor/tests/ -v`) confirming 45/45 tests pass with zero hardcoded workspace paths and fail-closed authentication intact
