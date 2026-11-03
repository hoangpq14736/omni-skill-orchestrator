---
description: "Granular, dependency-ordered task breakdown for DeepSeek-V4.1-Flash Strict Architecture Gatekeeper"
---

# Tasks: DeepSeek-V4.1-Flash Strict Architecture Gatekeeper (Omni-Auditor v4.1)

**Input Documents**: Design documents from `specs/002-deepseek-v41-auditor/` (`spec.md`, `plan.md`) and blueprint `PROJECT_DEEPSEEK_V41_AUDITOR.md`  
**Prerequisites**: `spec.md`, `plan.md`, `.specify/constitution.md`  
**Tests Included**: Yes (Executable Pytest suites in `specs/002-deepseek-v41-auditor/tests/`)  

## Format: `- [ ] [TaskID] [P?] [Story?] Description with exact file path`
- `[TaskID]`: Unique sequential execution identifier (`T001`, `T002`, ... `T040`).
- `[P]`: Flag indicating the task can execute concurrently in parallel (isolated files).
- `[Story]`: User story tag (`[US1]`, `[US2]`, `[US3]`). Omitted for Setup, Foundational, and Polish phases.
- Exact file paths are specified in all task descriptions.

---

## AI Worker Fleet Capability Allocation

| Worker Agent | Specialization & Tool Driver | Assigned Task Range | Rationale |
|---|---|---|---|
| **`local_worker_mi50`** | Surgical in-place file modifications (`fast_edit`), Python stdlib implementation, AST manipulation, local configuration, SQLite WAL logging (`l1_staging_log`), offline execution on AMD Instinct MI50 GPU (16GB HBM2 @ 1024 GB/s). | **T005 - T009, T011 - T017, T019 - T024, T027 - T033, T036 - T037** | 100% offline security, zero token consumption, sub-millisecond local disk edits, exact adherence to standard library constraints. |
| **`groq_worker_cloud`** | Ultra-high-throughput code synthesis (300-800+ tok/s), JSON-RPC MCP boilerplate generation, massive Pytest suite generation (`groq_generate_tests`, `groq_code_gen`), cross-artifact convergence audits (`analyze`) on Groq LPU cluster. | **T001 - T004, T010, T018, T025 - T026, T034 - T035, T038 - T040** | Near-zero latency for large scaffolding files, comprehensive edge-case test matrices, and multi-file convergence audits. |

---

## Phase 1: Setup & Scaffolding (Shared Infrastructure)

**Purpose**: Establish workspace directories, environment validation, test fixtures, and shared mock harnesses.

- [x] T001 Initialize feature test directory and configuration in `specs/002-deepseek-v41-auditor/tests/__init__.py`
- [x] T002 [P] Configure shared Pytest fixtures, mock HTTP servers, and fake DeepSeek API responses in `specs/002-deepseek-v41-auditor/tests/conftest.py`
- [x] T003 [P] Configure environment variable validation and AppLocker compatibility assertions in `specs/002-deepseek-v41-auditor/tests/test_environment.py`
- [x] T004 [P] Create synthetic flawed RFC and code diff fixtures in `specs/002-deepseek-v41-auditor/tests/fixtures/flawed_rfc.md` and `specs/002-deepseek-v41-auditor/tests/fixtures/flawed_diff.patch`

---

## Phase 2: Foundational Prerequisites (Blocking)

**Purpose**: Core security boundaries, credential sanitization, and stdlib HTTP foundations that MUST be verified before user story implementation.

**⚠️ CRITICAL**: No user story implementation work can proceed until this phase is complete and verified.

- [x] T005 Implement `DEEPSEEK_API_KEY` environment loader with zero-hardcoding enforcement and exit code 2 handling in `scripts/consult_critic.py`
- [x] T006 [P] Extend Zero-Trust credential redaction regex in `scripts/sanitizer.py` to scrub DeepSeek keys (`sk-[A-Za-z0-9_-]{20,}`), Anthropic keys (`sk-ant-[A-Za-z0-9_-]{20,}`), authorization Bearer tokens, GitHub PATs (`ghp_` and `github_pat_`), and unquoted/quoted `.env` assignments to `[REDACTED_*]` / `[REDACTED_SECRET]`
- [x] T007 [P] Implement workspace path canonicalization and directory traversal defense (`os.path.normcase`, `os.path.normpath`, `os.path.realpath`, `os.path.commonpath` root clamping) in `scripts/consult_critic.py`
- [x] T008 Implement full jitter exponential backoff formula $T_{\text{wait}} = \min(10.0, 1.0 \times 2^{\text{attempt}}) + \text{uniform}(0.1, 0.5)$ with 3-retry limit in `scripts/consult_critic.py`
- [x] T009 Implement standardized exit code mapping (0=Approved, 1=Critique Generated, 2=Auth/Quota, 3=Timeout, 4=Config, 5=System) in `scripts/consult_critic.py`

**Checkpoint**: Foundational security, sanitization, and backoff verified — User Story 1 implementation can now proceed.

---

## Phase 3: Milestone M1 — User Story 1: Zero-Dependency stdlib REST Client `consult_critic.py` (Priority: P1) 🎯 MVP

**Goal**: Deliver direct command-line interface client `scripts/consult_critic.py` calling DeepSeek API (`deepseek-v4.1-flash`) with 100% Python standard library (`urllib.request`), full Argon Bridge flag parity (`--prompt`, `--file`, `--out`, `--timeout`, `--mode`, `--strict`, `--json`), structured output formatting, and $<30.0\text{s}$ turnaround ceiling.

**Independent Test**: Execute `pytest specs/002-deepseek-v41-auditor/tests/test_consult_critic.py`; verify zero external dependencies, CLI argument parsing, Devil's Advocate persona injection, 3-retry backoff on HTTP 429/503, 30s timeout abortion, and output artifact persistence.

### Tests for User Story 1 (Author & verify first) ⚠️
- [x] T010 [P] [US1] Author executable Pytest test suite covering CLI parsing, stdlib imports only, prompt generation, backoff retries, and timeout handling in `specs/002-deepseek-v41-auditor/tests/test_consult_critic.py`

### Implementation for User Story 1
- [x] T011 [US1] Implement CLI argument parser with Argon parity (`--prompt`, `--file`, `--out`, `--timeout`, `--mode`, `--model`, `--temperature`, `--strict`, `--json`) in `scripts/consult_critic.py`
- [x] T012 [US1] Implement Red-Teaming "Devil's Advocate" system prompt templates for `--mode rfc` (architectural risks) and `--mode code` (race conditions, memory leaks) in `scripts/consult_critic.py`
- [x] T013 [US1] Implement zero-dependency `urllib.request.Request` payload serializer with custom User-Agent and JSON headers in `scripts/consult_critic.py`
- [x] T014 [US1] Implement HTTP response parsing, error status dispatching (401, 402, 429, 500, 503), and markdown review extraction in `scripts/consult_critic.py`
- [x] T015 [US1] Implement output artifact persistence with structured JSON metadata HTML comment header (`<!-- OMNI_AUDIT_META: {"verdict": "...", "target_file": "...", "input_hash": "...", "timestamp_utc": "..."} -->`) in `scripts/consult_critic.py`
- [x] T016 [US1] Implement credential scrubbing pass on all outbound user prompts via `scripts/sanitizer.py` in `scripts/consult_critic.py`
- [x] T017 [US1] Run benchmark validation to confirm critique turnaround $<30.0\text{s}$ and cold startup $<25\text{ms}$ in `specs/002-deepseek-v41-auditor/tests/test_consult_critic.py`

**Checkpoint**: User Story 1 (M1 MVP) is fully functional, independently verified, and satisfies all P1 requirements.

---

## Phase 4: Milestone M2 — User Story 3: Virtual MCP Server Driver `deepseek_worker_mcp.py` (Priority: P3)

**Goal**: Deliver a zero-dependency JSON-RPC 2.0 MCP server in `d:\Antigravity\DeepSeek Worker\deepseek_worker_mcp.py` providing `deepseek_audit_spec` and `deepseek_audit_diff` tools registered in `C:\Users\vuhuu\.gemini\config\mcp_config.json`.

**Independent Test**: Execute `pytest specs/002-deepseek-v41-auditor/tests/test_deepseek_mcp.py`; verify JSON-RPC 2.0 stdin/stdout protocol, tool discovery schema, `deepseek_audit_spec` execution, `deepseek_audit_diff` execution, and clean process termination on EOF.

### Tests for User Story 3 (Author & verify first) ⚠️
- [x] T018 [P] [US3] Author executable Pytest test suite for MCP stdio protocol, tool schema discovery, tool invocation, and error handling in `specs/002-deepseek-v41-auditor/tests/test_deepseek_mcp.py`

### Implementation for User Story 3
- [x] T019 [US3] Implement stdio JSON-RPC 2.0 server loop with stderr diagnostic logging, `sys.path.insert(0, ...)` for `scripts/`, and `ThreadPoolExecutor(max_workers=4)` in `d:\Antigravity\DeepSeek Worker\deepseek_worker_mcp.py`
- [x] T020 [US3] Implement `tools/list` handler declaring `deepseek_audit_spec` and `deepseek_audit_diff` tool schemas in `d:\Antigravity\DeepSeek Worker\deepseek_worker_mcp.py`
- [x] T021 [US3] Implement `deepseek_audit_spec` tool handler calling `consult_critic` engine in `d:\Antigravity\DeepSeek Worker\deepseek_worker_mcp.py`
- [x] T022 [US3] Implement `deepseek_audit_diff` tool handler calling `consult_critic` engine in `d:\Antigravity\DeepSeek Worker\deepseek_worker_mcp.py`
- [x] T023 [US3] Implement stdio serialization locking (`threading.Lock()`) to prevent interleaved responses during concurrent tool calls in `d:\Antigravity\DeepSeek Worker\deepseek_worker_mcp.py`
- [x] T024 [US3] Implement graceful shutdown handler on EOF and SIGINT in `d:\Antigravity\DeepSeek Worker\deepseek_worker_mcp.py`
- [x] T025 [US3] Register `deepseek_worker_cloud` MCP server configuration entry in `C:\Users\vuhuu\.gemini\config\mcp_config.json`
- [x] T026 [US3] Run end-to-end MCP protocol verification confirming valid tool calls and responses in `specs/002-deepseek-v41-auditor/tests/test_deepseek_mcp.py`

**Checkpoint**: User Story 3 (M2 MCP Tooling) is fully functional and accessible to Antigravity agents.

---

## Phase 5: Milestone M3 — User Story 2: Deterministic Gatekeeper Hook & Council Governance (Priority: P2)

**Goal**: Deliver deterministic pre-flight hard-gating in `scripts/hook_runner.py` intercepting RFC/SDD intents, executing two-state local filesystem artifact verification (`verify_critic_artifact`), injecting appropriate directive/review context into `injectSteps`, and enshrining Rule 6 Council Protocol in `rules/AGENTS.md`.

**Independent Test**: Execute `pytest specs/002-deepseek-v41-auditor/tests/test_gatekeeper_hook.py`; verify intent regex activation, filler bypass in $<1.0\text{ms}$, pre-flight subprocess turnaround $<25\text{ms}$, critique markdown injection, and zero echo-chamber enforcement.

### Tests for User Story 2 (Author & verify first) ⚠️
- [x] T027 [P] [US2] Author executable Pytest test suite for gatekeeper intent detection, fast-exit filler bypass, two-state disk artifact verification, and context injection in `specs/002-deepseek-v41-auditor/tests/test_gatekeeper_hook.py`

### Implementation for User Story 2
- [x] T028 [US2] Implement RFC and architecture intent detection regex (`/teamwork`, `RFC`, `FRC`, `spec.md`, `plan.md`) in `scripts/hook_runner.py`
- [x] T029 [US2] Implement fast filler bypass preservation guaranteeing $<1.0\text{ms}$ exit on conversational prompts in `scripts/hook_runner.py`
- [x] T030 [US2] Implement non-blocking decoupled filesystem artifact check (`CRITIC_REVIEW.md` mtime freshness, `OMNI_AUDIT_META` verdict parsing) and directive injection in `scripts/hook_runner.py` (strictly zero network calls during pre-flight, zero subprocesses)
- [x] T031 [US2] Implement two-state directive/review context injection (`[CRITICAL ARCHITECTURE GATEKEEPER DIRECTIVE]` if unreviewed/rejected; `[CRITICAL REVIEW FROM DEEPSEEK-V4.1-FLASH]` if approved) in `scripts/hook_runner.py`
- [x] T032 [US2] Implement telemetry logging of gatekeeper activation events into existing 7 columns of `l1_staging_log` in `scripts/hook_runner.py`
- [x] T033 [US2] Enshrine Rule 6 Council Protocol updating `rules/AGENTS.md` with DeepSeek-V4.1-Flash Council Gate and echo-chamber ban in `rules/AGENTS.md`

**Checkpoint**: User Story 2 (M3 Kernel Hard Gate) is fully integrated; unreviewed RFCs cannot complete without Gatekeeper audit.

---

## Phase 6: Milestone M4 — Verification, Cross-Cutting Hardening & Integration Test Suite

**Purpose**: Execute end-to-end integration tests, clean-room adversarial simulation with deliberate architectural flaws, verify zero credential leakage, and validate 100% Spec Kit convergence.

- [x] T034 Author end-to-end integration test executing flawed RFC audit and verifying rejection in `specs/002-deepseek-v41-auditor/tests/test_deepseek_auditor_e2e.py`
- [x] T035 [P] Author security audit test verifying zero credential leakage in logs, headers, or stdout in `specs/002-deepseek-v41-auditor/tests/test_credential_leakage.py`
- [x] T036 Run clean-room adversarial simulation: submit `flawed_rfc.md` through `consult_critic.py` and verify $\ge 3$ critical defects identified in `specs/002-deepseek-v41-auditor/tests/test_deepseek_auditor_e2e.py`
- [x] T037 Verify fail-closed auth gate: test that unsetting `DEEPSEEK_API_KEY` immediately aborts with exit code 2 (`EXIT_AUTH_QUOTA_ERROR`), emits bilingual diagnostics, fails closed, and strictly blocks legacy `consult_argon.py` echo-chamber fallback in `specs/002-deepseek-v41-auditor/tests/test_deepseek_auditor_e2e.py`
- [x] T038 Execute complete Pytest test suite across all milestones with 100% passing rate in `specs/002-deepseek-v41-auditor/tests/`
- [x] T039 Execute benchmark suite confirming $<25\text{ms}$ pre-flight hook turnaround and $<30.0\text{s}$ full critic turnaround in `specs/002-deepseek-v41-auditor/tests/`
- [x] T040 Run GitHub Spec Kit cross-artifact convergence audit (`analyze`) to confirm 100% alignment across `spec.md`, `plan.md`, `tasks.md`, and `checklist.md`

---

## Dependencies & Execution Order

### Phase Dependencies
1. **Setup (Phase 1)**: Can begin immediately; no dependencies.
2. **Foundational (Phase 2)**: Depends on Phase 1; **BLOCKS** all user story implementations.
3. **User Story 1 (Phase 3 - M1)**: Depends on Phase 2; implements core CLI client `consult_critic.py`.
4. **User Story 3 (Phase 4 - M2)**: Depends on Phase 3 (`consult_critic.py` core engine); implements MCP server.
5. **User Story 2 (Phase 5 - M3)**: Depends on Phase 3 (`consult_critic.py` CLI); implements hook gate in `hook_runner.py` and Rule 6.
6. **Integration & Validation (Phase 6 - M4)**: Depends on completion of Phases 3, 4, and 5; executes end-to-end verification.

### Within Each User Story
- Pytest test suites MUST be authored first and verified before runtime code modification.
- Data sanitization and path validation before network request execution.
- Performance benchmarks run to confirm SLA adherence before marking story complete.

---

## Task-to-Requirement Crosswalk Matrix

| Requirement | Description | Primary Tasks | Verification Test File |
|---|---|---|---|
| **FR-001** | Zero-Dependency Stdlib Client | T005, T008, T013 | `tests/test_consult_critic.py` |
| **FR-002** | Dual Audit Modes (`--mode rfc`, `--mode code`) | T011, T012 | `tests/test_consult_critic.py` |
| **FR-003** | Red-Teaming Anti-Praise Prompting | T012, T036 | `tests/test_consult_critic.py` |
| **FR-004** | Jittered Exponential Backoff Engine | T008, T014 | `tests/test_consult_critic.py` |
| **FR-005** | Deterministic Exit Codes (0-5) | T009, T014 | `tests/test_consult_critic.py` |
| **FR-006** | Structured JSON Mode (`--json`) | T011, T014, T015 | `tests/test_consult_critic.py` |
| **FR-007** | Performance Telemetry Logging | T015, T017 | `tests/test_consult_critic.py` |
| **FR-008** | Pre-Submission Secret Redaction | T006, T016, T035 | `tests/test_credential_leakage.py` |
| **FR-009** | Pre-Flight Intent Interception | T028, T030 | `tests/test_gatekeeper_hook.py` |
| **FR-010** | Slash Command Bypass Fix | T028, T029 | `tests/test_gatekeeper_hook.py` |
| **FR-011** | Context Injection Formatting | T031 | `tests/test_gatekeeper_hook.py` |
| **FR-012** | Standard-Library MCP Server | T019, T023, T024 | `tests/test_deepseek_mcp.py` |
| **FR-013** | MCP Tools Specification | T020, T021, T022 | `tests/test_deepseek_mcp.py` |
| **FR-014** | Council Protocol Enshrinement | T033 | `tests/test_gatekeeper_hook.py` |
| **FR-015** | 1M Context Window Processing | T013, T017 | `tests/test_consult_critic.py` |
| **NFR-001** | Audit Latency SLA (<30.0s) | T017, T039 | `tests/test_consult_critic.py` |
| **NFR-002** | Pre-Flight Hook SLA (<25ms) | T029, T039 | `tests/test_gatekeeper_hook.py` |
| **NFR-003** | Zero-Trust & AppLocker Compliance | T003, T007 | `tests/test_environment.py` |
| **NFR-004** | Zero External Dependencies Invariant | T001, T010 | `tests/test_consult_critic.py` |
| **NFR-005** | Physical VRAM Headroom Protection | T003, T013 | `tests/test_environment.py` |
| **NFR-006** | Strict Echo-Chamber Elimination | T033, T036 | `tests/test_deepseek_auditor_e2e.py` |
