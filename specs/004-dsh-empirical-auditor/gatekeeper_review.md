<!-- OMNI_AUDIT_META: {"verdict":"APPROVED","target_file":"spec.md","input_hash":"sha256:02613e91fe6178ab52fb1a833b1a94ef077c867ac34d4e7af75541240dcba475","model":"deepseek-flash","hash_domain":"raw_file_v1","hash_algo":"sha256-v2","timestamp_utc":"2026-11-10T20:02:12.004492+00:00","workspace_hash":"7845dcbea5badfa6ac16e154c2d7f2d5e46ce980a48500b822090dc90650930a","signature":"0a4966956cc88ac5f9806204f3c303b18dc27a5e04c4efecfef9948af1987ab3"} -->

# 🛡️ Architectural Red-Teaming Audit: spec.md
**Audit Status**: `APPROVED` | **Model**: `deepseek-flash` | **Confidence**: `0.94` | **Timestamp**: `2026-11-10T20:02:12.004492+00:00`

## Executive Summary
The specification is coherent, practical for a single-user local project, and does not contain a breaking functional contradiction. It is heavier than strictly necessary (MMPP, DWR, provenance ledger), but these mechanisms are self-contained, standard-library oriented, and directly address real Windows/DSH failure modes such as stale locks, pipe deadlocks, sandbox cleanup, and worktree isolation. Approve with incremental implementation guidance rather than enterprise hardening.

## 1. Constitutional & Ring 0 Invariants Verification
- ✅ Ring 0 Security (Zero-Trust SQL & Credential Redaction): PASS
- ✅ Principle I Reflex Latency Boundary: PASS
- ✅ Concurrency & Physical Resource Bounds: PASS

## 2. Top Critical Architectural Vulnerabilities (0 identified)
_No critical vulnerabilities identified. (Zero-defect floor verified)_

## 3. Concurrency, Race Condition & Mutex Hazards (5 identified)
- **Resource**: `.dsh_audit.lock` | **Hazard**: Stale lock, racing stale reclaim, or 0-byte lockfile due to interrupted writer | **Mitigation**: Use pre-staged payload plus direct atomic os.rename; heartbeat via atomic os.replace; nonce/PID/session ownership checks on release; two-phase .reclaim rename for stale locks; fail fast with LOCK_CONTENTION_TIMEOUT after retry deadline.
- **Resource**: `Windows anonymous pipes for DSH stdout/stderr/stdin` | **Hazard**: Child process blocks on full stderr pipe or silent hang blocks synchronous stdout iteration | **Mitigation**: Use the specified tri-thread I/O model and a threading.Timer watchdog that runs taskkill /F /T /PID; close stdin after writing; join daemon threads in finally.
- **Resource**: `Tier 2 sandbox directory and child processes` | **Hazard**: WinError 32 file handle contention during cleanup after successful audit | **Mitigation**: Terminate child process tree before deletion; use purge_directory_robust with retries and chmod read-only reset; defer persistent locks to scratch/.deferred_cleanups.txt; never delete failure evidence.
- **Resource**: `Git index and shadow worktrees` | **Hazard**: Stale .git/index.lock or worktree lock causes git worktree add/remove/checkout failures | **Mitigation**: Run ensure_git_index_unlocked before Git operations; purge only stale locks older than 30s after confirming no active git.exe; wrap worktree provisioning in jittered exponential backoff.
- **Resource**: `Repository files during Tier 1 or concurrent Agy activity` | **Hazard**: DSH or Agy mutates files while an audit is in flight | **Mitigation**: Take SHA-256 snapshots before/after; enforce nonce-bound lock ownership; Agy mutation hook checks .dsh_audit.lock; rollback unauthorized Tier 1 tracked-file changes and unlink unauthorized new files.

## 4. Defensive Failure Scenarios & Edge Cases (6 verified)
### 1. dsh.cmd is missing, DSH_CLI_PATH is invalid, or PATH resolution fails
- **Consequence**: Audit cannot start and may leave an acquired lock or temp file behind
- **Mitigation**: Resolve binary via DSH_CLI_PATH, shutil.which, then default LOCALAPPDATA path; on failure return AuditResult(success=False, error=DSH_BINARY_NOT_FOUND) without acquiring the lock or after clean release of any temp file.

### 2. DSH emits non-JSON garbage, partial NDJSON, or terminates before final event
- **Consequence**: Parser crash or lost diagnostic result
- **Mitigation**: Catch JSONDecodeError per line and log raw line to stderr diagnostics; if final is absent after EOF, synthesize fail-soft AuditResult with partial tool records and success=False.

### 3. Timeout fires while the main thread is blocked reading proc.stdout
- **Consequence**: Client hangs indefinitely despite configured timeout
- **Mitigation**: Use threading.Timer watchdog to run taskkill /F /T /PID; process-tree termination closes the anonymous pipe, unblocks stdout iteration, then proc.wait returns and TimeoutExpired is raised with partial diagnostics.

### 4. Tier 2 sandbox cleanup still hits WinError 32 after retries due to Defender or SearchIndexer
- **Consequence**: Sandbox directory remains on disk and disk usage grows silently
- **Mitigation**: Do not use ignore_errors=True; append sandbox path and PID to scratch/.deferred_cleanups.txt, return audit result cleanly, and process the entry during the next DWR startup sweep.

### 5. Tier 3 shadow worktree produces an empty diff because DSH made no changes
- **Consequence**: Empty patch file may be mistaken for audit failure
- **Mitigation**: Treat empty diff as a valid no-change outcome; still remove the worktree and set diff_patch_path to the empty patch or None; record that no mutation was produced.

### 6. Turn 2 supplies an expired, deleted, or corrupted --session-id
- **Consequence**: DSH emits an error and the multi-turn fix-verify loop stops
- **Mitigation**: Detect unknown-session error events, log a warning, strip --session-id, and retry once as a fresh Turn 1 while preserving the injected prompt and original task ID.

## 5. Prescriptive Remediation Directives (6 items)
- Implement in slices: first NDJSON parser, subprocess watchdog, and Tier 1; then Tier 2 sandboxing; then Tier 3 worktrees and MMPP provenance. Do not build all layers before proving the core dispatch loop works.
- Keep all state in local JSON/NDJSON files and the standard library; avoid adding databases, services, or third-party dependencies.
- Use absolute paths, UTF-8 encoding, and os.path.normcase(os.path.realpath(...)) for all path comparisons and lockfile identity checks.
- On every failure path, release or reclaim only owned locks, unlink private temp files, and return structured AuditResult errors instead of raising unhandled exceptions.
- Validate taskkill /F /T, os.rename lock semantics, taskkill on real process trees, and git worktree cleanup on the actual Windows 11 host before depending on them in production flows.
- Document manual recovery commands for stale .dsh_audit.lock, scratch/.deferred_cleanups.txt, and orphaned shadow worktrees so the single user can recover without reading source code.

## 6. Council Gate Final Verdict: `APPROVED`
