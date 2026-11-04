<!-- OMNI_AUDIT_META: {"verdict":"REJECTED","target_file":"Cluster 1: Memory Engine, Concurrency & SQLite WAL","input_hash":"sha256:09515baaaecc0e222b2870db31e66b213697751d5d4cd0fa8bd169eae605f7f6","model":"deepseek-flash","timestamp_utc":"2026-11-03T20:30:25.947779+00:00"} -->

# 🛡️ Architectural Red-Teaming Audit: Cluster 1: Memory Engine, Concurrency & SQLite WAL
**Audit Status**: `REJECTED` | **Model**: `deepseek-flash` | **Confidence**: `0.97` | **Timestamp**: `2026-11-03T20:30:25.947779+00:00`

## Executive Summary
REJECTED: The bundle contains multiple CRITICAL isolation, transaction, and single-writer defects. Most severe are cross-workspace leakage in hybrid_search, workspace-hash double-hashing and cross-workspace clustering in consolidation, unsafe explicit transactions in revert_invariant, and a MemorySingleWriter that neither enforces foreign keys nor propagates fatal worker failures. The WAL stress test does not cover these paths, so its PASS result is not evidence of production safety.

## 1. Constitutional & Ring 0 Invariants Verification
- ⚠️ Gatekeeper Finding: Invariant check issued verdict `REJECTED` with 10 vulnerability findings.

## 2. Top Critical Architectural Vulnerabilities (10 identified)
### 1. [CRITICAL] VULN-001: Cross-workspace data leak in hybrid_search hydration
**Description**: Dense candidates are selected with dense_embeddings.workspace_hash = ?, but final hydration selects workspace_episodic_memory only by memory_id IN (...) with no workspace_hash filter. A stale or malicious dense_embeddings row can associate a foreign memory_id with the current workspace, causing hybrid_search to return another workspace's episodic record. Consolidator also updates workspace_episodic_memory.workspace_hash without updating dense_embeddings.workspace_hash, making stale mappings likely.
**Remediation**: `Add AND workspace_hash = :ws_hash to the hydration query. Enforce a composite constraint/FK tying dense_embeddings.workspace_hash to the parent memory workspace, and update dense_embeddings.workspace_hash whenever workspace_episodic_memory.workspace_hash changes.`

### 2. [CRITICAL] VULN-002: Workspace hash double-hashing and cross-workspace promotion in consolidator
**Description**: drain_l1_staging inserts l1_staging_log.workspace_hash into activation_events.workspace_dir. consolidate_batch later treats that value as a filesystem path and calls canonical_workspace_hash(ws_dir) again. Promoted records therefore receive a hash-of-a-hash as workspace_hash and a hash string as workspace_path. Clustering also uses only fold_vietnamese(user_input) without workspace, so events from different workspaces can be merged and promoted as one global proven trace.
**Remediation**: `Preserve the original workspace_hash without rehashing, or actually store workspace_path in l1_staging_log/activation_events. Cluster by (workspace_hash, normalized_signature). Reject any promotion whose workspace cannot be validated.`

### 3. [CRITICAL] VULN-003: Unsafe explicit transaction in revert_invariant bypasses Single-Writer
**Description**: init_database defaults isolation_level to IMMEDIATE. revert_invariant executes BEGIN IMMEDIATE without checking conn.in_transaction, so it can fail with 'cannot start a transaction within a transaction'. It catches all exceptions, rolls back, and returns False with no diagnostic. It also writes directly on the caller connection, bypassing MemorySingleWriter and allowing concurrent writers to race.
**Remediation**: `Use a single transaction context manager, check conn.in_transaction and roll back before BEGIN, or route this write through MemorySingleWriter. Raise or log structured failure reasons instead of returning silent False.`

### 4. [CRITICAL] VULN-004: MemorySingleWriter lacks FK enforcement and fatal-error propagation
**Description**: The worker connection never sets PRAGMA foreign_keys=ON, so ON DELETE CASCADE for dense_embeddings is not guaranteed and orphan embeddings can accumulate. sqlite3.connect or initial PRAGMA failure before the worker loop kills the thread silently. enqueue_write/flush has no error channel, so flush() can hang forever. A callback that raises inside success or failure handling can also kill the worker or trigger a double callback.
**Remediation**: `Set PRAGMA foreign_keys=ON and all required pragmas on every connection. Capture worker startup and loop failures and fail all queued callbacks. Add worker liveness monitoring and bounded flush. Wrap callbacks so they cannot terminate the worker or double-fire.`

### 5. [HIGH] VULN-005: FTS5 orphan or duplicate rows with INSERT OR REPLACE
**Description**: workspace_episodic_memory has trigger-maintained FTS5 rows. INSERT OR REPLACE deletes conflicting rows, but SQLite fires DELETE triggers for REPLACE only when recursive_triggers is enabled. The test seed uses INSERT OR REPLACE, so stale FTS rows can remain or expected content can be missing.
**Remediation**: `Avoid INSERT OR REPLACE on FTS-backed tables. Use ON CONFLICT DO UPDATE or explicit UPDATE/INSERT. Enable PRAGMA recursive_triggers=ON if REPLACE must be supported, and add FTS reconciliation tests comparing source row count to episodic_fts row count.`

### 6. [HIGH] VULN-006: Swallowed exceptions leave partial vector-backfill transaction open
**Description**: consolidator wraps embedding backfill and WAL maintenance in broad try/except with pass. If get_embedding or dense_embeddings INSERT fails after a transaction has started, self.conn.commit() is skipped and no rollback occurs. Subsequent operations can run inside the same open transaction and commit partial backfill state. hybrid_search similarly skips corrupt blobs without diagnostics.
**Remediation**: `Use explicit try/except/rollback/finally for backfill. Log workspace, memory_id, model, and exception context. Fail the batch or mark the backfill as retryable. Do not swallow errors around vacuum/checkpoint without recording them.`

### 7. [HIGH] VULN-007: Cosine similarity silently accepts dimension mismatch
**Description**: cosine_similarity iterates over min(len(v1), len(v2)) and only checks norm == 0.0. Incompatible embedding dimensions produce a partial dot product and invalid ranking instead of an error. Stored norms are also not checked for finiteness or negativity.
**Remediation**: `Require len(v1) == len(v2), reject non-finite norms, and validate model/dimensions metadata before similarity. Treat corrupt or mismatched vectors as failed candidates with diagnostic logging.`

### 8. [HIGH] VULN-008: False proven-trace promotion from neutral feedback
**Description**: consolidate_batch skips only feedback_score < 0.0. Two neutral 0.0 events, or one success plus one neutral, are promoted as proven_trace. Combined with missing workspace in the cluster key, this creates false global proven memories.
**Remediation**: `Promote only when the cluster contains at least two events with feedback_score > 0.0. Include workspace_hash in the cluster key. Preserve evidence counts and require a success ratio threshold.`

### 9. [HIGH] VULN-009: Ebbinghaus SQL can set confidence_score to NULL
**Description**: Bulk decay uses MIN/MAX around julianday(last_accessed_at). If last_accessed_at is malformed, julianday returns NULL and scalar MAX/MIN propagate NULL, violating confidence_score NOT NULL and aborting the consolidation transaction. The formula also ignores existing confidence_score and can increase confidence for low-initial-confidence records.
**Remediation**: `Validate ISO-8601 timestamps at write time. Use COALESCE(julianday(last_accessed_at), julianday(created_at), julianday('now')) and explicit NULL guards. Model decay from existing confidence_score, not only activation_count, and ensure decay is monotonic non-increasing.`

### 10. [HIGH] VULN-010: Stale lock recovery can allow duplicate consolidators
**Description**: main acquires LifecycleGuard with stale_timeout_sec=60.0, but the daemon can run indefinitely and no heartbeat refresh is shown. After 60 seconds without lock refresh, a second process may consider the lock stale and run concurrent consolidation writes.
**Remediation**: `Implement an explicit heartbeat with lock mtime or content refresh, set stale timeout greater than the maximum expected batch duration, include PID and process start time, and prefer a database-level advisory lock or transaction-owned lock row.`

## 3. Concurrency, Race Condition & Mutex Hazards (6 identified)
- **Resource**: `SQLite write path (workspace_episodic_memory, l1_staging_log, activation_events)` | **Hazard**: Direct writes bypass MemorySingleWriter and revert_invariant uses an unsafe explicit BEGIN IMMEDIATE | **Mitigation**: Route all writes through one writer or enforce a strict write connection contract with in_transaction checks, busy_timeout, retry, and rollback-before-begin.
- **Resource**: `dense_embeddings and workspace_episodic_memory` | **Hazard**: workspace_hash mutation without dense row update; foreign_keys disabled on writer connection | **Mitigation**: Enable PRAGMA foreign_keys=ON on every connection, add composite workspace integrity constraints, and update dense rows atomically with parent workspace changes.
- **Resource**: `episodic_fts trigger synchronization` | **Hazard**: INSERT OR REPLACE may skip DELETE triggers and leave orphan or stale FTS rows | **Mitigation**: Use UPSERT or explicit delete/insert, enable recursive_triggers where needed, and run FTS row-count reconciliation after migrations and tests.
- **Resource**: `Consolidator daemon lifecycle lock` | **Hazard**: 60-second stale timeout without heartbeat allows duplicate consolidators | **Mitigation**: Heartbeat lock ownership, use a TTL longer than max batch time, include PID/start time, and add a database advisory lock for critical consolidation.
- **Resource**: `Vector backfill transaction` | **Hazard**: Broad exception handling skips rollback and leaves an open transaction | **Mitigation**: Use explicit rollback/finally, log failure context, and make backfill idempotent per memory_id.
- **Resource**: `WAL checkpoint and incremental vacuum` | **Hazard**: PASSIVE checkpoint can be starved by long readers and WAL can grow unbounded | **Mitigation**: Monitor WAL size, add checkpoint lag metrics, schedule TRUNCATE checkpoint during maintenance, and cap reader transaction duration.

## 4. Defensive Failure Scenarios & Edge Cases (8 verified)
### 1. sanitize_fts5_query returns an empty string for blank or punctuation-only input
- **Consequence**: search_fts5 builds a MATCH expression like content_exact : () and SQLite raises an OperationalError
- **Mitigation**: Return [] early when both sanitized queries are empty; validate FTS expressions before execute.

### 2. dense_embeddings contains a vector with a different dimension or a corrupt blob length
- **Consequence**: cosine_similarity computes a partial dot product or hybrid_search silently drops the candidate, producing wrong or incomplete ranking
- **Mitigation**: Strictly validate blob length, dimensions metadata, and norm finiteness; fail closed with diagnostic context.

### 3. last_accessed_at contains a malformed timestamp
- **Consequence**: julianday returns NULL, confidence_score becomes NULL, and the NOT NULL constraint aborts the consolidation batch
- **Mitigation**: Validate timestamps at write time and wrap julianday calls with COALESCE fallbacks and explicit NULL guards.

### 4. dense_embeddings.workspace_hash is stale relative to workspace_episodic_memory.workspace_hash
- **Consequence**: hybrid_search hydration returns a record from another workspace
- **Mitigation**: Filter hydration by workspace_hash and update dense_embeddings.workspace_hash in the same transaction as parent workspace changes.

### 5. two consolidator processes race after the lock file exceeds stale_timeout_sec
- **Consequence**: Duplicate promotion, double decay, and concurrent writes to activation_events and episodic memory
- **Mitigation**: Add heartbeat refresh, PID/start-time identity, and a database-level lock row or advisory mutex.

### 6. revert_invariant is called while the connection already has an implicit transaction open
- **Consequence**: BEGIN IMMEDIATE fails, rollback is attempted, and the function returns False without exposing the real cause
- **Mitigation**: Check conn.in_transaction, roll back safely before starting, or use a savepoint/context manager with structured error reporting.

### 7. feedback_score is 0.0 for multiple events in the same cluster
- **Consequence**: Neutral events are promoted as proven_trace and pollute retrieval
- **Mitigation**: Require feedback_score > 0.0 and a minimum success count before promotion.

### 8. caller passes limit=-1 or an extremely large limit to search_fts5
- **Consequence**: SQLite LIMIT -1 disables the limit and can cause unbounded result sets and memory pressure
- **Mitigation**: Clamp limit to a safe positive range and reject invalid values before query execution.

## 5. Prescriptive Remediation Directives (8 items)
- Fix workspace isolation first: add workspace_hash filtering to final hydration, preserve workspace_hash without rehashing, and cluster promotions by (workspace_hash, normalized_signature).
- Replace direct SQLite writes in revert_invariant and consolidator with the single-writer contract, or enforce a strict transaction API that checks conn.in_transaction and rolls back before BEGIN.
- Enable PRAGMA foreign_keys=ON and PRAGMA recursive_triggers=ON on every connection that writes workspace_episodic_memory or dense_embeddings, and add integrity checks for orphan embeddings and FTS row counts.
- Remove broad except/pass blocks around backfill, vacuum, checkpoint, callbacks, and vector corruption. Emit structured diagnostics with memory_id, workspace_hash, model_name, and exception text, then rollback or fail the batch.
- Validate all numeric and temporal inputs: embedding dimensions, finite norms, ISO-8601 timestamps, non-negative activation counts, and bounded limit values.
- Do not concatenate raw sanitized strings into FTS5 MATCH expressions. Tokenize and validate the query, reject empty or unsafe expressions, and wrap execution errors with query context.
- Promote traces only on positive feedback evidence, not neutral 0.0 feedback, and record the exact event IDs used for promotion.
- Add targeted tests for MemorySingleWriter worker death, revert_invariant transaction nesting, cross-workspace dense leakage, FTS REPLACE behavior, malformed timestamps, and duplicate consolidator acquisition. The existing WAL stress test does not exercise these failure paths.

## 6. Council Gate Final Verdict: `REJECTED`
