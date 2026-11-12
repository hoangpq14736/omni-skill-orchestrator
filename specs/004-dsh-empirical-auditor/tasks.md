# 004‑dsh‑empirical‑auditor – Tasks

## Phase 1 – Foundations
- [x] T001: Update `.gitignore` to exclude `.dsh_audit.lock`, `.agy_provenance.jsonl`, `scratch/`
- [x] T002: Implement Data Models, Enums & Dynamic Binary Discovery (`scripts/dsh_auditor.py`)
- [x] T003: Implement LockManager (MMPP Layer 1)
- [x] T004: Implement ProvenanceLedger (MMPP Layer 2)

## Phase 2 – Workspace & Context
- [x] T005: Implement DynamicWorkspaceResolver (tier routing, cleanup, worktree handling)
- [x] T006: Implement ContextInjector (redact credentials) & SessionManager
- [x] T007: Implement NDJSONStreamParser & tri‑thread streaming subprocess watchdog

## Phase 3 – Client & Test Suite
- [x] T008: Implement `DSHAuditorClient`, head‑less dispatch, retry logic, and CLI entry point
- [x] T009: Author comprehensive pytest suite (`tests/test_dsh_auditor.py`, `tests/test_dsh_auditor_client.py`)

## Phase 4 – Validation & Verification
- [x] T010: Run pytest suite and confirm 100 % pass
- [x] T011: Execute live empirical integration tests (Tier 1 read‑only, Tier 2 SQLite concurrency)
- [x] T012: Independent verification via sub‑agent & Gatekeeper diff audit (`scripts/consult_critic.py`)

### Worker Fleet Allocation

| Task | gemini_worker_cloud | groq_worker_cloud | local_worker_mi50 | verification_subagent |
|------|--------------------|-------------------|-------------------|------------------------|
| T001 | ✔ |   |   |   |
| T002 | ✔ |   |   |   |
| T003 | ✔ |   |   |   |
| T004 | ✔ |   |   |   |
| T005 |   | ✔ |   |   |
| T006 |   | ✔ |   |   |
| T007 |   | ✔ |   |   |
| T008 | ✔ |   |   |   |
| T009 |   |   | ✔ |   |
| T010 |   |   | ✔ |   |
| T011 |   |   | ✔ |   |
| T012 |   |   |   | ✔ |