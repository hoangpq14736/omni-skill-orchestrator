<!-- OMNI_AUDIT_META: {"verdict":"REJECTED","target_file":"omni_kernel_v41_full_campaign.patch","input_hash":"sha256:0163b3e3d11205d6024153b40828550df7d2a7bf08c8f9ef5fce2ecec2a35f3b","model":"deepseek-flash","hash_domain":"redacted_prompt_v1","hash_algo":"sha256-v2","timestamp_utc":"2026-11-04T16:05:14.233966+00:00","workspace_hash":"0f03e216b4ff8ec39315d4d9db720f619c14f85e5358e2aec11b48be314ab9eb","signature":"d6ce0c03aa29a3c81cdc71d79336327761abdb08a9c8dda45808cf8fc7df7b3a"} -->

# 🛡️ Architectural Red-Teaming Audit: omni_kernel_v41_full_campaign.patch
**Audit Status**: `REJECTED` | **Model**: `deepseek-flash` | **Confidence**: `0.93` | **Timestamp**: `2026-11-04T16:05:14.233966+00:00`

## Executive Summary
The remediation bundle is directionally good (parameterized SQL, atomic writes, CAS leases, redaction, FTS guards, teardown hardening) but still ships blocking correctness and reliability defects for a single-developer CLI. The most severe: (1) canonical_workspace_hash was switched to 64-hex SHA-256 while resolve_workspace_hash still detects only 32-hex and compares against a 64-hex root hash, so every new staging row is re-hashed as a filesystem path or quarantined — consolidation/recall breaks and existing MD5-keyed rows are orphaned with no migration; (2) is_transient_io_error recurses unbounded over __cause__ (self-referential causes crash the worker), reintroducing the exact VULN-001 already documented in this same bundle; (3) MemorySingleWriter evicts unreported write failures at >256, so flush() can return success after data loss; (4) the patch overwrites scripts/proven_traces.json with synthetic test traces and local C:\Users\vuhuu paths, poisoning the user's real recall and leaking PII; (5) the pre-flight hot path now does PRAGMA journal_mode=WAL, 1s busy_timeout, fsync+replace of telemetry, a 0.2s file-lock append, and up to ~33 file reads/HMAC checks per invocation, which cannot reliably meet the <25ms SLA under WAL contention. Additionally, the self-provisioned gatekeeper HMAC is not a trust boundary against the agent, the verdict schema is too shallow (crash with misleading exit 1), and lifecycle heartbeat swallows exceptions enabling split-brain. The bundle's own committed audits document REJECTED/CONDITIONAL findings that are not addressed here.

## 1. Constitutional & Ring 0 Invariants Verification
- ⚠️ Gatekeeper Finding: Invariant check issued verdict `REJECTED` with 9 vulnerability findings.

## 2. Top Critical Architectural Vulnerabilities (9 identified)
### 1. [CRITICAL] VULN-001: Workspace hash algorithm mismatch: 64-hex vs 32-hex detection causes quarantine/double-hashing and orphans legacy rows
**Description**: memory_utils.canonical_workspace_hash now returns 64-char SHA-256 and its idempotency short-circuit was removed. But consolidator.resolve_workspace_hash still gates the 'already a hash' branch on is_valid_hex_hash(cleaned, length=32) and then compares 32-hex input against canonical_workspace_hash(approved_root) which is 64-hex. hook_runner writes canonical_workspace_hash(workspace_dir) (64-hex) into l1_staging_log.workspace_hash; drain_l1_staging copies that into activation_events.workspace_dir. consolidate_batch then calls resolve_workspace_hash with a 64-hex string: the 32-hex branch is skipped, the value is treated as a filesystem path, and (a) with approved_root (scoped engine) commonpath fails -> every legitimate event is quarantined as is_consolidated=2 and no consolidation ever happens, or (b) with allow_unscoped it computes a cwd-dependent hash-of-hash that recall's canonical_workspace_hash(workspace_dir) can never match. Meanwhile all pre-existing MD5-keyed rows in omni_memory.db become unreachable because there is no re-key migration or dual-key read in the DB path.
**Remediation**: `In resolve_workspace_hash accept both 32 and 64 hex (is_valid_hex_hash(cleaned, length=None) plus authorized_hashes check for the 64-hex form) and compare against a root hash of the same length; store the canonical workspace_path alongside the hash in staging/activation_events if you need to re-derive it; ship a one-time migration that re-keys existing 32-hex workspace_hash rows to the new 64-hex value (or implement dual-key reads for at least one release); add an end-to-end test path->hash->staging->consolidate->recall asserting the same partition key is used.`

### 2. [CRITICAL] VULN-002: Unbounded recursion in is_transient_io_error over __cause__ crashes consolidation worker
**Description**: is_transient_io_error(err) recursively calls itself on err.__cause__ with no visited set and no depth limit. Python permits cyclic/self-referential exception chains (e.g. `raise e from e`, or wrapper libraries that chain causes cyclically). Any such error reaching flush_outbox/consolidate_batch triggers RecursionError, killing the worker and leaving outbox rows claimed InFlight until the 180s stale lease expires; the consolidation pipeline effectively hangs. This is exactly the VULN-001 documented in the bundle's own docs/audits/cluster_1_remediation_audit.md and is still not fixed.
**Remediation**: `Add a visited set of id(err) and a hard max depth (16) to is_transient_io_error; return False on revisit. Add a regression test constructing `e.__cause__ = e` and passing it through a record_trace failure path.`

### 3. [HIGH] VULN-003: MemorySingleWriter silently drops write failures via _failed_sequences eviction
**Description**: The worker bounds _failed_sequences to 256 and deletes min(keys) when exceeded. If more than 256 tasks fail before flush() is called, earlier failure records are removed; flush() checks only `s <= target_seq` on the remaining map and can return successfully even though writes failed. This is silent data loss disguised as a successful commit and violates the stated 'never swallow exceptions' invariant. Callback exceptions are also caught and only written to stderr, so flush() cannot surface them.
**Remediation**: `Never evict an unreported failure. Keep a dropped_failures_since_flush flag and raise from flush()/close() when set, or persist failures to a dead-letter store. Add a test that enqueues 300 failing writes before flush and asserts a non-zero error is reported.`

### 4. [HIGH] VULN-004: PreInvocation hot path now performs synchronous SQLite WAL switch, fsync, and file-lock operations, violating the <25ms SLA
**Description**: process_hook (per invocation) executes `PRAGMA journal_mode = WAL` (requires a lock on the DB and can block up to sqlite3 timeout=1.0 / busy_timeout=1000 ms, especially while the consolidator holds the WAL writer), commits a staging insert, writes last_activation.json with os.fsync + os.replace, appends history under TrustFileLock with a 0.2s timeout, and verify_critic_artifact can os.open/read/HMAC-verify up to ~33 candidate files (root 3 names, specs 3+15, docs/audits 15). Under WAL contention or a slow/AV-scanned disk the hook can block for seconds, breaking the advertised <25ms budget. The every-50-events subprocess.Popen is also on the hot path.
**Remediation**: `Set journal_mode=WAL once at database creation, not per hook. Use a short busy_timeout (<=50ms) with fail-open drop of telemetry, move last_activation/history writes to an async writer or detached process (and drop fsync on the hot path), bound the review-artifact scan (single dir, mtime cache, cheap pre-filter before HMAC), and spawn the consolidator from a non-blocking queue. Instrument p95/p99 and assert the SLA with a fault-injected busy writer.`

### 5. [HIGH] VULN-005: Patch overwrites live proven_traces.json with synthetic test fixtures and local PII
**Description**: The diff replaces scripts/proven_traces.json with thousands of test traces ('positive task query', 'clean valid command', 'cuda out of memory vram' with success_count 108, workspace_hash 'dddd...', etc.) plus real local paths such as C:\Users\vuhuu\AppData\Local\Temp\... and dummy/truncated redaction artifacts. On merge the developer's actual experiential memory is destroyed/poisoned: recall will return fake fixes, success_counts and last_recalled are meaningless, and local path PII is committed to the repo.
**Remediation**: `Do not version mutable state files. Add scripts/proven_traces.json (and jsonl telemetry, .lock files, DB files) to .gitignore; move seed data to tests/fixtures; provide an explicit reset/migration command instead of replacing the live file; scrub any absolute user paths from committed artifacts.`

### 6. [HIGH] VULN-006: Council Gate HMAC key is self-provisioned by the same UID/agent and weak key-file checks make the gatekeeper advisory only
**Description**: sign_audit_meta() auto-provisions ~/.gemini/config/omni_audit.key on first producer call; the agent (same UID) can invoke consult_critic.py or read/write that file, so it can mint a validly signed APPROVED artifact. _verify_key_file_security accepts tempfile.gettempdir() as a valid key location and uses raw str.startswith containment (sibling-dir confusion, e.g. /home/bob vs /home/bobby), and its GetNamedSecurityInfoW call requests OWNER_SECURITY_INFORMATION then discards the SID, so it validates nothing. verify_critic_artifact also scans docs/audits/*.md, so any signed artifact dropped in the workspace can authorize work. In a personal CLI this is tamper-evidence, not an enforcement boundary.
**Remediation**: `Either label the gatekeeper as advisory and require explicit human approval for APPROVED, or keep the signing key outside any path the agent can read/write and require an explicit operator provisioning step (never auto-provision from an agent-invocable script); use os.path.commonpath for containment and drop the temp-dir exception; validate the DACL owner SID correctly or remove the call; do not scan arbitrary workspace docs for approvals without binding to canonical target + session nonce.`

### 7. [HIGH] VULN-007: Shallow verdict schema causes unhandled crash with misleading exit code 1
**Description**: validate_audit_verdict does not type-check confidence_score (later used as f"{confidence:.2f}") nor that items in critical_vulnerabilities/concurrency_hazards/edge_cases are dicts (later accessed with .get). A model response such as {"confidence_score":"high"} or {"critical_vulnerabilities":["race"]} passes validation, then format_markdown_report raises TypeError/AttributeError and Python exits 1, which is EXIT_CRITIQUE_GENERATED. Machine consumers therefore cannot distinguish 'critique produced' from 'process crashed'. Additionally MIN_TIMEOUT=5.0 is below MIN_INFER_WINDOW=8.0, so `--timeout 5` always exits 3 on the first 429/5xx with zero retries.
**Remediation**: `Implement full validation: confidence_score float in [0,1]; each finding a dict with non-empty id/severity/title/description/remediation; enum checks. Wrap format_markdown_report in try/except and exit EXIT_SYSTEM_STRICT with context. Set MIN_TIMEOUT = MIN_INFER_WINDOW + 1.0 and reject out-of-range --timeout with exit 4 (no silent clamp).`

### 8. [HIGH] VULN-008: Lifecycle heartbeat swallows all exceptions and live processes can be reclaimed (split-brain)
**Description**: _start_heartbeat()._beat() wraps the entire CAS/atomic-write body in `except Exception: pass`. A persistent failure (mutex timeout, fsync error, JSON decode of a concurrently replaced lock file) stops heartbeat refreshes while the process is fully alive. acquire_lock then reclaims when `is_alive and is_heartbeat_stale`, so a second consolidator/MCP instance starts concurrently with the first, racing on SQLite and state files. release_lock also swallows failures and may leave an orphaned lock. This is a concrete multi-process hazard even on a single developer machine (daemon + manual CLI).
**Remediation**: `Count consecutive heartbeat failures; after N, set a degraded/stop flag, log with persist_diag, and refuse to release ownership silently. Never reclaim a live PID solely on heartbeat age unless a DB advisory/fencing token proves the old owner cannot write. Remove `except: pass` from the heartbeat and release paths; add a two-process contention test.`

### 9. [MEDIUM] VULN-009: Outbox CAS generation mismatch leaves rows InFlight with no lease_mismatch recovery
**Description**: flush_outbox claims rows (SELECT generation), does file I/O, then UPDATEs with `AND COALESCE(generation,1) = ?`. If ON CONFLICT re-promotion bumps generation between Phase 1 and Phase 3, the CAS rowcount is 0 and the row stays InFlight with the old owner_token for up to the 180s stale lease. There is no lease_mismatch handling, so retry is delayed and, with a generation-fencing mismatch, reinforcement can be duplicated. The docstring claims deterministic CAS recovery but the code does not implement it.
**Remediation**: `In Phase 3, if the CAS UPDATE affects 0 rows, log lease_mismatch and either reset the row to Pending in a separate CAS on (status, owner_token) or mark it for immediate retry; add a test that bumps generation concurrently between claim and commit.`

## 3. Concurrency, Race Condition & Mutex Hazards (7 identified)
- **Resource**: `omni_memory.db write path (l1_staging_log insert vs consolidator WAL writer)` | **Hazard**: Per-invocation PRAGMA journal_mode=WAL plus busy_timeout=1000ms on the pre-flight hot path; under daemon write contention the hook blocks up to 1s, violating <25ms | **Mitigation**: Set journal_mode=WAL once at DB creation; use busy_timeout<=50ms and drop telemetry best-effort; move staging inserts to a queue in the daemon; assert the SLA with a fault-injected concurrent writer.
- **Resource**: `consolidation_outbox (InFlight lease)` | **Hazard**: Generation bump between claim and CAS commit leaves row InFlight (rowcount=0) for 180s; no deterministic recovery, possible duplicate reinforcement | **Mitigation**: Handle rowcount=0 as lease_mismatch: reset to Pending under (status, owner_token) CAS or mark retryable; fencing token checked in both DB and file.
- **Resource**: `LifecycleGuard PID lockfile / heartbeat` | **Hazard**: Heartbeat CAS body swallows exceptions; stale-heartbeat reclaim of an alive PID produces two 'exclusive' instances (split-brain) writing SQLite and state | **Mitigation**: Do not swallow heartbeat errors; set degraded state; require a fencing/DB advisory token before reclaiming a live PID; log and test two-process contention.
- **Resource**: `mcp_gateway module cache (_CACHED_MCP_INDEX / _MCP_LOCK)` | **Hazard**: Full filesystem reindex performed while holding _MCP_LOCK, blocking all concurrent resolver calls (hot path) for the duration of the scan | **Mitigation**: Use single-flight reindex with an immutable snapshot swapped atomically, compute outside the lock, and keep the lock only for the pointer swap; bound reindex cost and TTL.
- **Resource**: `activations_history.jsonl appends and rotation` | **Hazard**: TrustFileLock timeout=0.2s on the hot path silently drops audit lines under contention; os.replace rotation races with concurrent readers/writers not holding the lock | **Mitigation**: Use a single writer/queue, per-PID shard files, or a longer off-hot-path timeout; never drop entries silently — fall back to a secondary shard and log.
- **Resource**: `_PROCESS_LOCKS map in experiential_memory` | **Hazard**: One permanent threading.RLock per distinct lock path; unbounded growth in a long-lived daemon (memory leak) | **Mitigation**: Bound with an LRU/refcount or weakref so unused per-path RLocks are reclaimed.
- **Resource**: `Nested SAVEPOINT handling in drain/consolidate/revert_invariant` | **Hazard**: On exception the ROLLBACK TO SAVEPOINT / RELEASE are themselves wrapped in `except: pass`; if they fail, an implicit transaction can stay open holding locks | **Mitigation**: Log rollback failures with context; on rollback failure force a connection-level rollback/reset; never leave an implicit transaction open.

## 4. Defensive Failure Scenarios & Edge Cases (10 verified)
### 1. An exception with a self-referential __cause__ (raise e from e) reaches is_transient_io_error
- **Consequence**: RecursionError kills the flush/consolidation worker; outbox rows remain InFlight until the 180s lease and the pipeline stalls
- **Mitigation**: Visited-set by id() + max depth 16; unit test with a cyclic cause.

### 2. More than 256 MemorySingleWriter writes fail before flush() is called
- **Consequence**: flush() returns success although writes were lost (silent data loss)
- **Mitigation**: Track dropped_failures_since_flush and raise in flush()/close(), or persist to a dead-letter store; test with 300 failures.

### 3. Model returns "confidence_score": "high" or a string item in critical_vulnerabilities
- **Consequence**: validate_audit_verdict accepts it, format_markdown_report raises TypeError/AttributeError, process exits 1 which is EXIT_CRITIQUE_GENERATED
- **Mitigation**: Strict type validation and wrap formatting; exit EXIT_SYSTEM_STRICT(5) with context on malformed output.

### 4. `--timeout 5` is passed (MIN_TIMEOUT) while MIN_INFER_WINDOW=8.0
- **Consequence**: The first 429/5xx immediately exits 3 with no retries; valid user requests are always rejected
- **Mitigation**: Set MIN_TIMEOUT = MIN_INFER_WINDOW + 1.0 and return exit 4 for out-of-range values instead of clamping.

### 5. No HMAC key file exists on a fresh machine (verifier path)
- **Consequence**: verify_audit_meta fails closed for every artifact; every Council Gate review silently becomes UNREVIEWED with only a persist_diag line, and no APPROVED path is reachable
- **Mitigation**: Surface a single actionable user-visible diagnostic (path + provisioning step); document that producer must provision out-of-band; do not let auto-provision be reachable from the agent.

### 6. last_activation.json os.replace or fsync fails (Windows AV holds the file, ENOSPC)
- **Consequence**: Telemetry becomes stale/silently lost; with the current catch-all it is only a persist_diag line and the user sees no problem while observability claims are false
- **Mitigation**: Log with context and retry off the hot path; do not block/fail the pre-flight; expose a health check.

### 7. A registry skill entry has specificity/quality_score of None or a non-numeric string
- **Consequence**: _candidate_sort_key does int(None) -> TypeError, crashing resolve_skill for any prompt that reaches sorting
- **Mitigation**: Coerce defensively (int(x or 0) with try/except default) and validate registry values at index time.

### 8. load_registry finds a corrupt registry and rebuild via build_index fails (permission/disk full)
- **Consequence**: The quarantining handler calls build_index and lets the exception propagate, crashing the resolver instead of returning default/degraded results
- **Mitigation**: Wrap the rebuild in try/except and return an empty registry with a loud diagnostic; keep the original file quarantined.

### 9. A workspace-provided docs/audits/*.md contains a validly signed APPROVED artifact for a different target/session
- **Consequence**: verify_critic_artifact may return APPROVED for unrelated work (audit replay), and because the key is self-provisionable the agent can mint such artifacts
- **Mitigation**: Bind approval to canonical target + prompt/content hash + nonce and require explicit human confirmation; treat the HMAC as tamper-evidence only.

### 10. synthesizer.run_sandbox_validation is called with allow_exec=True and hostile test_code
- **Consequence**: The subprocess inherits filesystem/network access and only a narrowed env; AST gating is trivially bypassed with getattr/subprocess, so this is not a sandbox
- **Mitigation**: Keep allow_exec default False; if execution is required, use a real OS sandbox or require explicit human approval on each test payload; rename the function to reflect it only validates AST.

## 5. Prescriptive Remediation Directives (10 items)
- Fix the hash pipeline first: accept 64-hex in resolve_workspace_hash, compare same-length root hashes, add a re-key migration (or dual-read) for existing 32-hex rows, and add an end-to-end path->hash->consolidate->recall test.
- Add a visited set + depth cap to is_transient_io_error before anything else; this is a known, still-open defect already documented in the bundle's own audit file.
- Never evict unreported MemorySingleWriter failures; surface them from flush()/close() or persist a dead-letter, and stop swallowing callback exceptions.
- Stop writing to proven_traces.json in the patch: gitignore mutable state (DB, locks, traces, telemetry) and move test seeds to fixtures; scrub C:\Users\... paths from artifacts.
- Take SQLite PRAGMA journal_mode=WAL off the per-invocation hot path, use a short busy_timeout with fail-open telemetry, drop fsync from the hook, and move history/last_activation writes off the <25ms path.
- Make the Council Gate honest: either label it advisory and require human approval for APPROVED, or require out-of-band key provisioning not reachable by the agent; replace startswith containment with os.path.commonpath, drop %TEMP% as a key location, and validate the DACL owner SID or remove the call.
- Harden validate_audit_verdict to type-check confidence_score and every list item, wrap format_markdown_report, and map malformed model output to EXIT_SYSTEM_STRICT instead of an accidental exit 1; fix MIN_TIMEOUT vs MIN_INFER_WINDOW.
- Remove all 'except Exception: pass' from lifecycle heartbeat/release, assimilator scans, resolver registry rebuild, and lock-cleanup paths; replace with persist_diag context or propagation, and add a split-brain contention test for LifecycleGuard.
- Handle flush_outbox CAS rowcount=0 as lease_mismatch with deterministic Pending reset, and add a generation-bump race test.
- Add a startup self-check endpoint/CLI that reports: WAL mode, busy_timeout, HMAC key availability, proven_traces.json integrity, and lock/outbox pending counts — so silent degradation is visible to the single developer.

## 6. Council Gate Final Verdict: `REJECTED`
