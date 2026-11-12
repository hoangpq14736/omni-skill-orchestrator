# Technical Implementation Plan: DSH Empirical Peer Auditor (`004-dsh-empirical-auditor`)

**Spec Reference**: [`specs/004-dsh-empirical-auditor/spec.md`](spec.md) (`APPROVED`, Confidence: `0.94-0.96`)  
**Target Module**: `scripts/dsh_auditor.py`  
**Test Suite**: `tests/test_dsh_auditor.py`

---

## 1. Technical Stack & Zero-Dependency Invariants
- **Runtime**: Python 3.11+ Standard Library only (AppLocker-proof, zero `pip install` dependencies).
- **Windows Kernel APIs**: `ctypes.windll.kernel32` (`OpenProcess(0x1000)`, `GetExitCodeProcess == 259`, `CloseHandle`) for deterministic process liveness checks without handle false positives; Win32 `MoveFileW` via `os.rename()` for atomic lockfile creation; `taskkill /F /T /PID` for process-tree teardown.
- **Reuse**: Imports `redact_credentials` from `scripts/sanitizer.py` (with graceful fallback regex if invoked standalone).

---

## 2. Module Topology (`scripts/dsh_auditor.py`)

| Component | Responsibility | Spec Alignment |
|---|---|---|
| **Domain Models & Enums** | `WorkspaceTier`, `AuditCategory`, `AuditTask`, `AuditResult`, `LockPayload`, `SweepReport`, `ProvenanceRecord`, `SessionState` | Sec 6.2 |
| **`LockManager` (MMPP L1)** | Pre-staged `.tmp` + `fsync` + direct atomic `os.rename`, 0-byte stale `>5.0s` purge, two-phase `.reclaim` CAS, daemon `.hb.tmp` heartbeat, strict nonce/pid/session release | Sec 5.1, FR-011/012 |
| **`ProvenanceLedger` (MMPP L2)** | `normcase(realpath())` path keys, `IGNORE_DIRS` cache exclusion, `mtime`-cached SHA-256 snapshots, blind overwrite rollback (`safe_git_checkout` + `os.unlink`), `.agy_provenance.jsonl` | Sec 5.2, FR-013..015 |
| **`DynamicWorkspaceResolver` (DWR)** | Startup sweep (`FR-021`), 7-category tier routing, Tier 1 In-Place, Tier 2 Scratch Sandbox (`--add-dir` + evidence retention on FAIL + `purge_directory_robust`), Tier 3 Shadow Git Worktree (`safe_git_worktree_add` + `ensure_git_index_unlocked` + patch harvest) | Sec 4, FR-006..010, FR-021 |
| **`ContextInjector` & `SessionManager`** | Boundary invariant prompt header + `redact_credentials`; `scratch/dsh_sessions.json` turn & token tracking | Sec 5.3, FR-016/017/019 |
| **`NDJSONStreamParser` & Streaming I/O** | 8-event FSM (`session`, `status`, `thinking`, `tool_call`, `tool_result`, `text`, `final`, `error`), Tri-Thread I/O (`stdin` feeder, `stderr` drainer, `stdout` reader) + `threading.Timer` watchdog | Sec 3.3, FR-001..005 |
| **`DSHAuditorClient` & CLI** | Full lifecycle orchestration, EC-013 unknown-session retry, backwards-compatible `run_empirical_audit()`, dual `--json` / human CLI (`main()`) | Sec 6.3, FR-018/020 |

---

## 3. Verification & Empirical Testing Strategy
1. **Unit & Concurrency Tests (`tests/test_dsh_auditor.py`)**:
   - Mocked `dsh.cmd` NDJSON streaming (normal turn, malformed lines EC-007, unknown session retry EC-013, abrupt EOF EC-015).
   - Real Windows NTFS concurrency tests for `LockManager` (contention backoff, 0-byte stale >5s purge, dead PID reclaim, non-matching release refusal).
   - Real `ProvenanceLedger` snapshot delta, Tier 1 mutation detection + rollback, and `.agy_provenance.jsonl` emission.
   - Real `DynamicWorkspaceResolver` Tier 2 purge/retention/deferred sweep and Tier 3 Git worktree isolation + patch harvest.
   - Real Watchdog timeout test killing a hanging subprocess tree and breaking pipe blocking immediately.
2. **Live End-to-End Empirical Integration Tests**:
   - Execute real `dsh.cmd` via `scripts/dsh_auditor.py` in Tier 1 (`--read-only`) and Tier 2 (`scratch/test_concurrency_issue.py` multi-turn session continuation).
3. **Independent Verification & Gatekeeper Audit**:
   - Subagent independent audit + `scripts/consult_critic.py` DeepSeek-V4.1-Flash review.
