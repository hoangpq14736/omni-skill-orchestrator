<!-- OMNI_AUDIT_META: {"verdict":"REJECTED","target_file":"Cluster 2: Pre-Flight Hook, Latency & IPI Sanitizer","input_hash":"sha256:2edf426fd644fc86dc858e71dd33b5b057232fa67cae6ba112614acca126fdaf","model":"deepseek-flash","timestamp_utc":"2026-11-03T20:31:51.391626+00:00"} -->

# 🛡️ Architectural Red-Teaming Audit: Cluster 2: Pre-Flight Hook, Latency & IPI Sanitizer
**Audit Status**: `REJECTED` | **Model**: `deepseek-flash` | **Confidence**: `0.94` | **Timestamp**: `2026-11-03T20:31:51.391626+00:00`

## Executive Summary
REJECTED. The cluster fails the stated security, SLA, and concurrency invariants. Critical defects include 64-bit Windows HANDLE truncation, lockfile ownership corruption/deletion, unsigned gatekeeper review artifacts with basename-only TOCTOU binding, unsanitized workspace-derived content injected into the agent pre-flight message, non-atomic trust/telemetry/lock writes, and synchronous SQLite plus disk writes on the <25ms hot path. The regex-only IPI sanitizer is also bypassable and is not integrated into hook_runner.

## 1. Constitutional & Ring 0 Invariants Verification
- ⚠️ Gatekeeper Finding: Invariant check issued verdict `REJECTED` with 9 vulnerability findings.

## 2. Top Critical Architectural Vulnerabilities (9 identified)
### 1. [CRITICAL] VULN-001: 64-bit Windows HANDLE truncation in LifecycleGuard
**Description**: lifecycle_guard.py calls kernel32.OpenProcess, WaitForSingleObject, and CloseHandle without setting ctypes restype/argtypes. On 64-bit Windows, OpenProcess returns a 64-bit HANDLE but ctypes defaults to 32-bit c_int. This can truncate live handles, mark live processes dead, fail to detect parent termination, close invalid handles, or leave orphan daemons. The same defect exists in is_process_alive and start_parent_watcher.
**Remediation**: `Set kernel32.OpenProcess.restype = wintypes.HANDLE and define argtypes; do the same for WaitForSingleObject and CloseHandle. Test on 64-bit Windows with long-lived parent processes and access-denied cases.`

### 2. [CRITICAL] VULN-002: PID lockfile mutual exclusion can be corrupted or deleted by a non-owner
**Description**: LifecycleGuard heartbeat writes lock JSON with open(r+), seek, and truncate without atomic replace. release_lock unlinks the lockfile unconditionally when JSON parsing fails, even if another process owns it. acquire_lock can also leave an empty or partial lockfile if json.dump fails after os.open. This permits duplicate daemons or permanent stale locks.
**Remediation**: `Write lock and heartbeat payloads to a temp file, fsync, and atomically os.replace them. On release, unlink only when pid equals os.getpid(); never unlink on parse failure. Add file-level locking and concurrency tests.`

### 3. [CRITICAL] VULN-003: Gatekeeper review artifact bypass via unsigned metadata and basename-only TOCTOU checks
**Description**: verify_critic_artifact trusts any workspace CRITIC_REVIEW.md or AUDIT_REVIEW.md containing OMNI_AUDIT_META with verdict APPROVED. There is no signature or reviewer authenticity check. Matching uses only basename(target_file). If target_file is None, any APPROVED artifact is accepted. If target_file is specified but missing on disk, mtime and hash validation are skipped entirely. An attacker can forge approval or reuse a review for a different path with the same basename.
**Remediation**: `Require signed review artifacts or HMAC over target path, hash, verdict, and timestamp. Canonicalize with os.path.realpath. Require exact canonical target path binding, require target_file to exist, require input_hash, and reject inline_prompt unless explicitly allowed by a trusted policy.`

### 4. [CRITICAL] VULN-004: Unsanitized workspace-derived content injected into pre-flight system message
**Description**: hook_runner builds ephemeralMessage from resolution fields including inferred_rules, skill descriptions, MCP tool descriptions, proven traces, and gatekeeper meta target_file. These values can originate from workspace rule files. AssimilatorGuard.scan_rules is not called here. A malicious workspace can inject instructions, newlines, markdown fences, or tool-call directives directly into the agent context.
**Remediation**: `Route every workspace-derived string through a positive allowlist and sanitizer before injection. Strip control characters and newlines, clamp lengths, escape markdown, and inject only signed or explicitly trusted rule content. Never interpolate raw MCP descriptions or review metadata without escaping.`

### 5. [HIGH] VULN-005: Non-atomic trust DB read-modify-write enables lost updates and corruption
**Description**: workspace_sanitizer.py add_trusted_workspace and remove_trusted_workspace perform an unlocked read-modify-write of trusted_workspaces.json. Concurrent processes can lose trust entries, truncate the JSON file, or leave it unparsable. The file is also written directly with no fsync or atomic replace. is_trusted_workspace then fails closed silently, causing denial of service or inconsistent trust decisions.
**Remediation**: `Use an exclusive file lock plus temp-file write, fsync, and os.replace. Validate JSON schema on read. Return explicit diagnostics on corruption instead of silent False.`

### 6. [HIGH] VULN-006: Non-atomic telemetry writes and no credential redaction in hook_runner
**Description**: last_activation.json is truncated and rewritten directly on every hook invocation. activations_history.jsonl is appended without cross-process locking. Concurrent hooks can interleave or corrupt telemetry. Full user_input up to 2048 characters is persisted without regex credential redaction, including potential tokens, passwords, and API keys. File permissions are not restricted.
**Remediation**: `Redact credentials before logging. Set 0600 permissions where supported. Use temp file plus os.replace for last_activation.json. For JSONL, use a single writer, file lock, or per-session file. Rotate and bound history size.`

### 7. [CRITICAL] VULN-007: Git safety check is bypassed for nested rule files and skill writes are non-atomic
**Description**: patch_workspace_rules calls is_git_busy_or_unsafe(path.parent). For rules/AGENTS.md, path.parent is the rules directory, so the .git marker check misses the actual repository root and can write during merge, rebase, or cherry-pick. sync_kernel_skills then writes SKILL.md directly with open(w) instead of atomic replace. A crash or concurrent sync can truncate or corrupt skill files.
**Remediation**: `Resolve the repository root by walking upward until .git is found, handling .git files for worktrees. Use atomic temp-file plus os.replace for every SKILL.md write. Create missing parent directories before mkstemp. Add per-file locking for concurrent sync.`

### 8. [HIGH] VULN-008: Synchronous SQLite and disk writes on the <25ms pre-flight hot path
**Description**: hook_runner performs a synchronous SQLite insert, a synchronous last_activation.json rewrite, and a history append on every invocation. The connection uses a 5-second busy timeout and never sets PRAGMA journal_mode=WAL, despite the WAL claim. Under lock contention the hook can block for up to 5 seconds. Multiple bare except Exception: pass blocks swallow failures, so SLA breaches and data loss are invisible.
**Remediation**: `Move telemetry and staging inserts to an asynchronous writer queue or detached process. If SQLite must remain inline, enable WAL, set busy_timeout to 100-250ms, retry with jitter, and log failures with context. Remove silent exception swallowing in the hook path.`

### 9. [HIGH] VULN-009: Regex-only IPI sanitizer is bypassable and is not a trust boundary
**Description**: workspace_sanitizer.py uses a denylist of English and Vietnamese phrases. Common IPI payloads such as 'print the previous instructions', 'act as the system administrator', 'repeat the text above', or obfuscated payloads using homoglyphs, zero-width characters, string concatenation, and alternate HTTP clients can pass. The sanitizer is not invoked by hook_runner, so its bypasses directly affect the pre-flight injection path.
**Remediation**: `Treat sanitizer output as untrusted and combine denylisting with positive allowlisting, content normalization, Unicode normalization, length limits, and signed trusted rules. Add adversarial IPI tests and integrate the sanitizer into every workspace-content ingestion path.`

## 3. Concurrency, Race Condition & Mutex Hazards (6 identified)
- **Resource**: `LifecycleGuard PID lockfile` | **Hazard**: Non-atomic heartbeat writes and non-owner unlink on parse error | **Mitigation**: Atomic temp-file replace for lock and heartbeat, fsync, pid ownership verification, file locking, no unlink on JSONDecodeError.
- **Resource**: `omni_memory.db staging inserts` | **Hazard**: Multiple hook processes contend for SQLite write lock with a 5s busy timeout and no WAL mode | **Mitigation**: Enable WAL, shorten busy_timeout, serialize writes through a single writer or queue, retry with jitter, and instrument lock wait times.
- **Resource**: `trusted_workspaces.json` | **Hazard**: Unlocked read-modify-write causes lost updates or truncated JSON | **Mitigation**: Exclusive file lock plus atomic replace, schema validation, and explicit corruption diagnostics.
- **Resource**: `kernel_sync target rule files and SKILL.md` | **Hazard**: Concurrent read-modify-write and direct overwrite can lose user edits or corrupt files | **Mitigation**: Per-file locks, optimistic mtime/hash checks, atomic temp-file replace, and fsync of file and parent directory.
- **Resource**: `activations_history.jsonl` | **Hazard**: Concurrent append writes can interleave on Windows and produce invalid JSONL | **Mitigation**: Single-writer process, file lock, per-process log files, or atomic line append with O_APPEND validation.
- **Resource**: `PID liveness checks` | **Hazard**: PID reuse, zombie processes, and PermissionError on os.kill are treated as dead | **Mitigation**: Store process creation time or start token, treat PermissionError as alive, reap zombies with waitpid, and require heartbeat plus creation-time match before reclaiming locks.

## 4. Defensive Failure Scenarios & Edge Cases (10 verified)
### 1. Malformed or oversized stdin JSON is sent to hook_runner
- **Consequence**: sys.stdin.read() is unbounded, so a large payload can exhaust memory or violate the 25ms SLA before the 2048-character clamp is applied
- **Mitigation**: Enforce a maximum stdin byte limit, reject malformed JSON with a diagnostic, and clamp before parsing nested fields where possible.

### 2. target_file does not exist when verify_critic_artifact runs
- **Consequence**: mtime and hash checks are skipped, so an APPROVED review for the same basename can authorize unrelated or missing work
- **Mitigation**: Require target_file to exist and require exact canonical path plus signed input_hash before returning APPROVED or CONDITIONAL_PASS.

### 3. OMNI_AUDIT_META block exceeds the first 512 bytes
- **Consequence**: Metadata is truncated, JSON parsing fails, and a valid review is silently treated as UNREVIEWED, causing false gatekeeper failures
- **Mitigation**: Parse only the bounded header but allow a larger documented metadata budget, or fail with an explicit diagnostic instead of silent UNREVIEWED.

### 4. 64-bit Windows process handle is truncated by ctypes
- **Consequence**: Live parent process is not detected, orphan daemon remains, or CloseHandle affects an invalid handle
- **Mitigation**: Set ctypes restype/argtypes for OpenProcess, WaitForSingleObject, GetExitCodeProcess, and CloseHandle, then test on 64-bit Windows.

### 5. A PID is reused by an unrelated live process after the original lock owner dies
- **Consequence**: Stale lock may be treated as live, or a live unrelated process may be treated as the owner, causing duplicate instances or denied startup
- **Mitigation**: Store process creation time or a random lock token; verify both PID and token before declaring ownership; use heartbeat and stale timeout together.

### 6. os.kill(pid, 0) raises PermissionError for a live process owned by another user
- **Consequence**: is_process_alive returns False, so a live lock can be reclaimed and a duplicate daemon can start
- **Mitigation**: Treat PermissionError as alive; only ProcessLookupError should mean dead on POSIX.

### 7. Git merge or rebase is active in the repository root while rules/AGENTS.md is patched
- **Consequence**: The nested path check misses the repository git state and writes workspace rules during an unsafe operation
- **Mitigation**: Resolve the true repository root before checking MERGE_HEAD, rebase-merge, rebase-apply, CHERRY_PICK_HEAD, REVERT_HEAD, and index.lock.

### 8. Antivirus or another process holds the target file open on Windows NTFS
- **Consequence**: os.replace fails after three short retries, the JIT patch is not persisted, and the temp file may be removed without user-visible recovery
- **Mitigation**: Use a bounded but longer exponential backoff, preserve a recovery journal, and report a clear diagnostic with the target path and retry state.

### 9. Trust store is concurrently modified by two add-trusted-workspace calls
- **Consequence**: One trusted entry is lost or the JSON file is truncated, causing inconsistent sanitizer bypass behavior
- **Mitigation**: Use an exclusive cross-process lock and atomic replace, then validate the resulting JSON before reporting success.

### 10. functools.lru_cache holds a negative workspace-vitals result for five minutes after Cargo.toml or k8s appears
- **Consequence**: Newly added high-risk workspace markers are not detected until the epoch bucket rotates, causing a temporary Tier 1 false negative
- **Mitigation**: Shorten the epoch bucket, invalidate on workspace mtime change, or use a bounded cache with explicit invalidation hooks.

## 5. Prescriptive Remediation Directives (10 items)
- Do not merge this cluster until all CRITICAL findings are fixed and regression-tested.
- Fix all Win32 ctypes bindings with explicit restype and argtypes, especially OpenProcess, WaitForSingleObject, GetExitCodeProcess, and CloseHandle.
- Make every lockfile, trust DB, telemetry file, and skill write atomic via temp file, fsync, and os.replace; add cross-process file locking.
- Replace unsigned review artifacts with signed or HMAC-authenticated metadata and exact canonical target path binding. Require target existence and input_hash.
- Sanitize and allowlist every workspace-derived string before injecting it into ephemeralMessage; strip control characters, newlines, markdown fences, and oversized fields.
- Move SQLite staging and telemetry off the synchronous pre-flight path or enable WAL with a short busy timeout; remove bare except Exception: pass from security and data-integrity paths.
- Fix Git safety detection to locate the repository root and handle .git worktree files; create missing parent directories before atomic writes.
- Add credential redaction and restrictive file permissions for persisted prompts and activation history.
- Add adversarial tests for IPI bypass, forged OMNI_AUDIT_META, stale review TOCTOU, PID reuse, permission-denied liveness, concurrent lock acquisition, and Windows 64-bit handle behavior.
- Instrument end-to-end hook latency with p95/p99 metrics and fail open only with explicit, durable diagnostic logging.

## 6. Council Gate Final Verdict: `REJECTED`
