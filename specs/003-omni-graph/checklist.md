# Operational Quality Gates: Omni-Graph (Graphify) Codebase Topology Engine

**Purpose**: Reviewer-owned operational quality checklist verifying storage integrity, AST extraction fidelity, signature contract precision, sub-millisecond traversal performance, autonomous zero-config bootstrapping, zero-dependency environment compliance, and zero regression across Omni-Kernel v4.1.  
**Created**: 2026-11-08  
**Feature**: `specs/003-omni-graph/` (`spec.md`, `plan.md`, `tasks.md`)  
**Review Ownership**: Reviewer-owned requirements-quality review artifact. Mark an item `[x]` only when verified against passing test evidence.  
**Marker Semantics**: `[x]` indicates that the criterion has been reviewed and verified against authoritative requirements.  

---

## Category 1: Storage & WAL Integrity

- [ ] **CHK001** [Storage Isolation & Zero-Conflict Duality] Does `<workspace>/.omni/codebase_graph.db` operate with dedicated SQLite WAL pragmas and complete physical/logical isolation from global `omni_memory.db`?
  - **Criterion**: Database must initialize at `<workspace>/.omni/codebase_graph.db` with `PRAGMA journal_mode = WAL;`, `PRAGMA synchronous = NORMAL;`, `PRAGMA busy_timeout = 5000;`, and `PRAGMA foreign_keys = ON;`. Omni-Memory operates on global cognitive history (`omni_memory.db`), while Omni-Graph operates strictly on workspace topology (`codebase_graph.db`). No shared database files, no shared mutexes, and zero cross-database ATTACH queries.
  - **Pass Threshold**: 100% compliance. Multi-threaded concurrent readers execute simultaneously with background writers without contention or deadlocks.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_storage.py -k "test_wal_pragmas_and_isolation" -v
    ```

- [ ] **CHK002** [Relational Schema & Foreign Key Cascades] Do all core tables enforce referential integrity and cascading deletes upon file modification?
  - **Criterion**: Tables `codebase_files_meta` (with `file_hashes` compatibility view), `nodes`, `signatures`, `edges`, and `lifecycle_hooks` must be created. Deleting a record from `codebase_files_meta` must automatically cascade delete all associated rows in `nodes`, `signatures`, `edges`, and `lifecycle_hooks`.
  - **Pass Threshold**: Zero orphaned child records after file deletion or re-parse. Verified by asserting count of dependent rows equals zero following parent record deletion.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_storage.py -k "test_foreign_key_cascades" -v
    ```

- [ ] **CHK003** [Git Hygiene Invariant] Does the storage engine automatically ensure `<workspace>/.omni/` is present in `<workspace>/.gitignore`?
  - **Criterion**: Upon initialization or bootstrap sweep, Omni-Graph must inspect `<workspace>/.gitignore`. If `.omni/` or `.omni` is not present, it must append `.omni/` with comment `# Omni-Kernel workspace artifacts` without altering existing rules or creating duplicates.
  - **Pass Threshold**: `<workspace>/.gitignore` contains `.omni/`. Git status shows `.omni/codebase_graph.db` as untracked/ignored.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_storage.py -k "test_git_hygiene" -v
    ```

---

## Category 2: AST Extraction & Contract Guard Accuracy

- [ ] **CHK004** [AST Signature Extraction Fidelity] Does the signature extractor accurately map Python 3.11+ parameter structures and tail-aligned defaults?
  - **Criterion**: Must correctly extract `posonlyargs`, standard `args`, tail-aligned default value counts ($N_{\text{req\_pos}} = N_{\text{pos}} - \text{len}(\text{defaults})$), `vararg` (`*args`), `kwonlyargs`, boolean default indicators for keyword-only parameters (`kw_defaults`), and `kwarg` (`**kwargs`).
  - **Pass Threshold**: 100% exact parameter match against a comprehensive test suite of 50 diverse Python function signatures (including modern Python 3.11 features).
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_ast_extractor.py -k "test_signature_extraction_fidelity" -v
    ```

- [ ] **CHK005** [Static Signature Contract Verification across 8 Failure Modes] Does the Signature Contract Guard statically detect all 8 contract failure modes without code execution?
  - **Criterion**: Must flag FAIL-01 (`TOO_MANY_POSITIONAL_ARGS`), FAIL-02 (`MISSING_REQUIRED_POSITIONAL_ARG`), FAIL-03 (`UNEXPECTED_KEYWORD_ARG`), FAIL-04 (`POSITIONAL_ONLY_AS_KEYWORD`), FAIL-05 (`MULTIPLE_VALUES_FOR_ARG`), FAIL-06 (`MISSING_REQUIRED_KEYWORD_ARG`), FAIL-07 (`RENAMED_PARAMETER_DRIFT`), and FAIL-08 (`UN_AWAITED_ASYNC_CALL`).
  - **Pass Threshold**: 100% detection rate across all 8 failure modes on synthetic test fixtures (including exact reproduction of SVBot incident `allocated_ram` vs `ram`). Zero false positives on valid variadic (`*args`, `**kwargs`) signatures.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_contract_guard.py -k "test_all_eight_failure_modes" -v
    ```

- [ ] **CHK006** [Lifecycle Registration Guard & Dangling Hook Detection] Does the Lifecycle Registration Guard detect orphaned implementations and dead dispatch references?
  - **Criterion**: Must flag declared framework handlers/commands lacking required registration edges (e.g. Discord slash commands without `tree.sync()`) and central dispatch dictionary entries pointing to deleted or renamed functions.
  - **Pass Threshold**: Correctly identifies 100% of orphaned hooks and dead registry references in test repositories. Emits actionable diagnostic warnings with exact file paths and line numbers.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_lifecycle_guard.py -k "test_lifecycle_drift_detection" -v
    ```

---

## Category 3: Blast Radius Traversal Performance (<0.30ms)

- [ ] **CHK007** [Sub-0.30ms Recursive CTE Execution SLA] Do transitive reverse caller queries execute in $<0.30\text{ms}$ on a 1,000-node graph?
  - **Criterion**: Transitive caller query (`WITH RECURSIVE blast_radius ...`) must utilize covering index `idx_edges_tgt_rel` and complete with mean execution time $\le 0.25\text{ms}$ and P99 $< 0.30\text{ms}$ for depth up to 5 hops.
  - **Pass Threshold**: P99 traversal latency $< 0.30\text{ms}$ across 1,000 iterations on a benchmark graph of 1,000 nodes and 3,000 edges.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_traversal.py -k "test_blast_radius_latency_benchmark" -v
    ```

- [ ] **CHK008** [Cycle-Safe Traversal Termination Invariant] Does the recursive CTE terminate cleanly on cyclic graphs without infinite loops or stack overflow?
  - **Criterion**: The CTE traversal query must include delimiter-safe cycle-prevention path filtering (`instr(path_tokens, '|' || node_id || '|') = 0`) using pipe token isolation and recursion depth clamping (`depth < max_depth`), preventing both infinite recursion loops and false-cutoff prefix collisions.
  - **Pass Threshold**: Traversal terminates in $<0.50\text{ms}$ on mutually recursive structures (`A -> B -> A`, `A -> B -> C -> A`, and self-recursive `A -> A`) without raising database errors, exceeding memory bounds, or truncating non-cyclic prefix matches.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_traversal.py -k "test_cycle_safe_termination or test_delimiter_safe_cycle_detection" -v
    ```

- [ ] **CHK009** [Risk-Tiered Impact Scoping Accuracy] Does the blast radius engine partition affected callers into deterministic risk tiers?
  - **Criterion**: Must classify callers into Tier 1 (Direct Callers, hop distance = 1), Tier 2 (Transitive Callers, hop distance $\in [2, 3]$), and Tier 3 (Cascading Ripple, hop distance $> 3$).
  - **Pass Threshold**: 100% mathematical accuracy against ground-truth graph topological distance calculations.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_traversal.py -k "test_risk_tiering_accuracy" -v
    ```

---

## Category 4: Zero-Dependency & Environment Isolation

- [ ] **CHK010** [100% Python Standard Library Compliance] Is the entire core engine of Omni-Graph implemented exclusively with Python 3.11+ standard library modules?
  - **Criterion**: Core modules under `plugins/omni-skill-orchestrator/scripts/omni_graph/` must import only standard library modules: `ast`, `sqlite3`, `pathlib`, `re`, `hashlib`, `json`, `os`, `sys`, `time`, `typing`. Zero third-party packages (`networkx`, `tree-sitter`, `pygraphviz` strictly prohibited).
  - **Pass Threshold**: Static AST import scan across all engine source files verifies zero external packages.
  - **Verification Command**:
    ```powershell
    python -c "import ast, sys, pathlib; files = list(pathlib.Path('plugins/omni-skill-orchestrator/scripts/omni_graph').glob('*.py')); imports = set(); [imports.update([n.names[0].name.split('.')[0] for n in ast.walk(ast.parse(f.read_text(encoding='utf-8'))) if isinstance(n, ast.Import)] + [n.module.split('.')[0] for n in ast.walk(ast.parse(f.read_text(encoding='utf-8'))) if isinstance(n, ast.ImportFrom) and n.module]) for f in files]; non_std = imports - sys.stdlib_module_names - {'omni_graph'}; assert not non_std, f'Disallowed external dependencies detected: {non_std}'; print('PASSED: 100% Python Standard Library')"
    ```

- [ ] **CHK011** [Windows AppLocker & Non-Elevated Execution] Does the entire graph toolchain execute under standard non-privileged Windows user privileges without DLL injection?
  - **Criterion**: Must run cleanly under Windows PowerShell without requiring administrator privileges, custom binary drivers, or unsigned native C-extension DLL loads.
  - **Pass Threshold**: Exits 0 on environment audit under standard Windows non-elevated user token.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_environment.py -k "test_applocker_compliance" -v
    ```

- [ ] **CHK012** [Offline Zero-CDN Visualization Contract] Does `graph.html` generate as a self-contained offline artifact with zero external network requests?
  - **Criterion**: `graph.html` must inline all HTML, CSS, and Canvas/JavaScript logic. Zero `<script src="http...">` or `<link href="http...">` tags.
  - **Pass Threshold**: Regex scan on generated `graph.html` matches zero instances of `http://` or `https://`. File opens and animates cleanly in an air-gapped browser with network disabled.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_visualizer.py -k "test_zero_cdn_offline_contract" -v
    ```

---

## Category 5: Backward Compatibility, Bootstrapping & Hook SLA (<25ms)

- [ ] **CHK013** [Autonomous Cold Start JIT Discovery (<100ms)] Does Omni-Graph automatically bootstrap missing workspace databases on first turn in $<100\text{ms}$?
  - **Criterion**: If `<workspace>/.omni/codebase_graph.db` does not exist when Step 0 Gatekeeper executes, it must automatically create the directory, initialize SQLite schema, and perform initial AST sweep without requiring manual user commands.
  - **Pass Threshold**: Cold start sweep for standard repository (up to 100 Python files) completes in $<100.0\text{ms}$. Database ready for immediate query.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_kernel_integration.py -k "test_autonomous_cold_start_bootstrap" -v
    ```

- [ ] **CHK014** [Pre-Flight Incremental Delta Check (<2ms) & Post-Edit Self-Healing (<15ms)] Does the pre-flight hook verify freshness in $<2\text{ms}$ and does post-edit self-healing update touched files in $<15\text{ms}$?
  - **Criterion**: Checking file modification timestamps against `codebase_files_meta` must execute in $<2.0\text{ms}$ during pre-flight. Following any tool file edit, the self-healing hook must re-parse only the modified file and update SQLite in $<15.0\text{ms}$.
  - **Pass Threshold**: Pre-flight delta check $<2.0\text{ms}$. Post-edit self-healing $<15.0\text{ms}$. Hook runner total OS subprocess budget strictly $<25.0\text{ms}$.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_kernel_integration.py -k "test_delta_check_and_self_healing_latency" -v
    ```

- [ ] **CHK015** [Zero-Conflict Concurrency with Omni-Memory v4.1] Do Omni-Memory v4.1 daemons and Omni-Graph CLI operations execute concurrently without lock contention or deadlocks?
  - **Criterion**: Simultaneous multi-process execution of Tier 3 consolidation on `omni_memory.db` and full codebase re-indexing on `codebase_graph.db` must complete with zero `sqlite3.OperationalError: database is locked` failures.
  - **Pass Threshold**: 100 concurrent iterations across separate threads and processes succeed with zero lock exceptions.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_zero_conflict_concurrency.py -v
    ```

---

## Category 6: Gatekeeper Council Critic Mitigations & Robustness (DeepSeek-V4.1-Flash)

- [ ] **CHK016** [Method Parameter Stripping (`self`/`cls`) & Unbound Call Receiver Compensation] Does `SignatureContractValidator` correctly strip receiver arguments on bound method calls without false `FAIL-02` positives AND compensate for explicit receiver arguments on unbound class calls without false `FAIL-01` positives?
  - **Criterion**: When validating bound method calls (`obj.method(...)`), the validator must strip `self` (instance method) or `cls` (`@classmethod`) from required positional parameters. `@staticmethod` must retain all parameters. When validating unbound class calls (`Class.method(instance, ...)` with `is_unbound_class_call=True`), the validator must apply receiver compensation (`effective_pos_count = max(0, pos_count - 1)` for instance methods) so the explicit receiver argument does not exceed positional capacity or trigger false-positive `FAIL-01`.
  - **Pass Threshold**: 100% accuracy across bound, unbound, static, and class methods: zero false-positive `FAIL-02` errors on bound calls and zero false-positive `FAIL-01` errors on unbound class calls.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_contract_guard.py -k "test_method_receiver_normalization or test_unbound_class_call" -v
    ```

- [ ] **CHK017** [Explicit Edge Deletion & Orphan Sweep Invariant] Does file modification or deletion atomically purge all associated edges without leaving phantom callers?
  - **Criterion**: Reindexing transactions must explicitly execute `DELETE FROM edges WHERE file_path = ?;` alongside `DELETE FROM codebase_files_meta WHERE file_path = ?;`. Orphan edge sweeps must purge any remaining dangling edges. CLI must support `--rebuild`.
  - **Pass Threshold**: Assert count of edges originating from modified or deleted file equals zero immediately following transaction. Zero phantom callers reported in blast radius queries.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_storage.py -k "test_explicit_edge_cleanup_and_orphan_sweep" -v
    ```

- [ ] **CHK018** [Delimiter-Safe Cycle Detection in Recursive CTE] Does recursive CTE traversal isolate node IDs with delimiter tokens to prevent prefix/substring false cycle cutoffs?
  - **Criterion**: Both `blast_radius` and `callee_tree` CTE queries must store paths using pipe delimiters (`'|' || id || '|'`) and evaluate cycle prevention via `instr(path_tokens, '|' || id || '|') = 0`.
  - **Pass Threshold**: Traversal achieves 100% recall on graphs containing colliding prefix identifiers (e.g. `scripts/foo.py:foo` and `scripts/foo.py:foobar`), with zero premature cutoffs or false-negative omissions.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_traversal.py -k "test_delimiter_safe_cycle_detection" -v
    ```

- [ ] **CHK019** [Non-Destructive In-Flight Syntax Error Fault Isolation] Do files with temporary syntax errors during editing fail gracefully without crashing the agent loop or wiping valid cached nodes?
  - **Criterion**: Files with syntax errors must be caught by `try...except SyntaxError`, marked with `parse_status = 'SYNTAX_ERROR'` in `codebase_files_meta`, and retain previous valid AST nodes with an advisory warning tag.
  - **Pass Threshold**: Full scan exits 0 with structured warning log. PreInvocation hook and resolver continue functioning normally without raising unhandled exceptions.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_ast_extractor.py -k "test_syntax_error_fault_isolation" -v
    ```

- [ ] **CHK020** [Display Path Casing Preservation & Unicode NFC Normalization] Does Omni-Graph maintain dual path representations and normalize all identifiers to Unicode NFC?
  - **Criterion**: `codebase_files_meta` and `nodes` must store lowercase normalized paths in `file_path`/`id` for stable cross-platform indexing, while preserving original filesystem casing in `display_path` for user-facing reports. All strings must be normalized to Unicode NFC before hashing and comparison.
  - **Pass Threshold**: All Markdown reports and visualizers output the exact filesystem casing while database lookups remain case-insensitive and diacritic-safe.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_storage.py -k "test_display_path_and_unicode_nfc" -v
    ```

- [ ] **CHK021** [Read-Only Advisory Hook Fail-Soft & 100ms Timeout SLA] Does the PreInvocation advisory hook execute under read-only pragmas with strict 100ms timeout bounds and zero blocking?
  - **Criterion**: The hook in `scripts/hook_runner.py` must open `codebase_graph.db` with URI `mode=ro` and `PRAGMA busy_timeout = 100;`. All database operations must be wrapped in `try...except` fail-soft blocks.
  - **Pass Threshold**: Under active exclusive write locks or database unavailability, hook execution completes in $<1.5\text{ms}$ with zero raised exceptions and zero degradation of agent responsiveness.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_kernel_integration.py -k "test_hook_advisory_fail_soft_under_lock" -v
    ```

- [ ] **CHK022** [Phased MVP Implementation Gate (Core vs Phase 2 Separation)] Can the Core Engine (Phase 1) be fully implemented, verified, and operated independently of Phase 2 visualization and reports?
  - **Criterion**: Storage, AST extraction, signature contract validation, delimiter-safe blast radius, and hook advisory must have zero functional dependencies on `graph.html`, `graph_report.md`, or `registration_invariants.json`.
  - **Pass Threshold**: 100% of Phase 1 test suite passes in headless, terminal-only test runs without HTML or report artifacts present.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/003-omni-graph/tests/test_mvp_core_isolation.py -v
    ```

- [ ] **CHK023** [Hardened Signature Contract Guard (The 4 Adversarial Fixes)] Does `SignatureContractValidator` pass all 4 adversarial edge cases identified during red-team testing?
  - **Criterion**: Must successfully validate:
    1. **GAP-1 (`FAIL-07` parameter drift)**: Accepts `renamed_params: dict[str, str]` and emits `FAIL-07` when a caller passes a deprecated parameter name, distinct from generic `FAIL-03`.
    2. **GAP-2 (Unbound class calls)**: Correctly applies receiver compensation (`is_unbound_class_call`), avoiding false `FAIL-01`.
    3. **GAP-3 (PEP 570 `**kwargs`)**: When `**kwargs` is present, positional-only parameter names passed as keywords are captured into keyword arguments without emitting `FAIL-04`.
    4. **GAP-4 (Single-violation emission)**: When a required positional-only argument is passed as a keyword, emits only `FAIL-04` and suppresses redundant `FAIL-02`.
  - **Pass Threshold**: 100% pass rate across the 16 adversarial empirical test fixtures in `tests/test_omni_graph_validator_empirical.py`.
  - **Verification Command**:
    ```powershell
    python -m pytest tests/test_omni_graph_validator_empirical.py -v
    ```

- [ ] **CHK024** [Stop-Point Zero-Regression Invariant: DeepSeek Auditor Suite (45/45)] Does the entire pre-existing test suite for `specs/002-deepseek-v41-auditor/` pass cleanly with zero regressions?
  - **Criterion**: Execution of the complete DeepSeek Auditor test suite must verify that `scripts/consult_critic.py` maintains zero hardcoded workspace paths, enforces fail-closed authentication (exit code 2 when `DEEPSEEK_API_KEY` is missing), and passes all unit, integration, and E2E mock tests.
  - **Pass Threshold**: 45/45 tests passing (0 failures, 0 errors, 100% pass rate) under standard Windows non-elevated environment.
  - **Verification Command**:
    ```powershell
    python -m pytest specs/002-deepseek-v41-auditor/tests/ -v
    ```


