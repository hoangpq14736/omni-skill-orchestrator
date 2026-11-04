<!-- OMNI_AUDIT_META: {"verdict":"REJECTED","target_file":"Cluster 4: Specifications & SDD Blueprints","input_hash":"sha256:4e84971f7d74d012e2693e7e77f2568e69a57fbeb6db92d88203225f7a3f9679","model":"deepseek-flash","timestamp_utc":"2026-11-03T20:34:53.636445+00:00"} -->

# 🛡️ Architectural Red-Teaming Audit: Cluster 4: Specifications & SDD Blueprints
**Audit Status**: `REJECTED` | **Model**: `deepseek-flash` | **Confidence**: `0.93` | **Timestamp**: `2026-11-03T20:34:53.636445+00:00`

## Executive Summary
Cluster 4 violates multiple non-negotiable constitutional invariants. The 'deterministic hard gatekeeper' is trivially spoofable: hook_runner trusts an unsigned plaintext OMNI_AUDIT_META header and never recomputes input_hash, so any agent can fabricate an APPROVED artifact and bypass NFR-006. Principle I.4 (no synchronous disk I/O in Tier 1) is contradicted by Principle I.2's l1_staging_log write, which additionally risks a 5,000ms busy_timeout stall inside a <25ms subprocess SLA. Principle V's bounded Ebbinghaus model is mathematically self-contradictory: the constitution locks S_0=1.0 while spec 001 uses S_0 varying (0.15) and the DDL exposes variable confidence_score, making pruning thresholds non-deterministic; the negative-delta-t blow-up is clamped only in EC-005, not in the decay entry point. The latency claims in Scenario 2.3 (<0.50ms for 1,000×384-dim dot products) and NFR-002 (<15ms at 10,000 records) are physically impossible under the mandated Python-stdlib-only baseline (NFR-004). Additional HIGH defects: basename fallback in target_file verification breaches workspace partition isolation; JSON-mode floor (FLAW-001) is only softly prompted with no client-side schema-enforcement FR; activation_events lacks workspace_hash; global synchronous=NORMAL can lose 'permanent' invariants on power loss; the deepseek-v4.1-flash model identifier is likely non-existent and the silent deepseek-chat fallback misrepresents the auditor identity. Bundle must be re-issued with signed artifacts, reconciled decay semantics, and realistic performance budgets before implementation.

## 1. Constitutional & Ring 0 Invariants Verification
- ⚠️ Gatekeeper Finding: Invariant check issued verdict `REJECTED` with 7 vulnerability findings.

## 2. Top Critical Architectural Vulnerabilities (7 identified)
### 1. [CRITICAL] VULN-001: Gatekeeper approval artifact is unsigned and trivially forgeable
**Description**: Scenario 2.1 and FR-009/FR-011 describe hook_runner verifying a plaintext HTML comment header `<!-- OMNI_AUDIT_META: {"verdict":"APPROVED", ...} -->` by existence, mtime, target_file string, and verdict enum only. Nothing binds the artifact to an actual DeepSeek response: no HMAC/key withheld from the agent process, no nonce, no review-body hash. Any agent can write a compliant header and pass the gate. The input_hash field is parsed but never recomputed against the current target file, leaving only an mtime guard that `touch`/file-copy defeats. This nullifies NFR-006 and FR-014 (echo-chamber elimination).
**Remediation**: `consult_critic.py MUST emit an HMAC-SHA256 signature over {target_file canonical path, SHA-256(target content), verdict, timestamp_utc, SHA-256(review body)} using a key stored in Windows DPAPI/Credential Manager inaccessible to the agent harness. hook_runner MUST recompute SHA-256 of the current target file, compare to meta.input_hash, and verify the HMAC; fail closed (inject GATEKEEPER REJECTION) on any mismatch. Add adversarial test: agent-authored header without valid signature must be rejected.`

### 2. [CRITICAL] VULN-002: L1 hook performs synchronous DB write, violating Principle I.4 and risking 5,000ms SLA blowout
**Description**: Principle I.4 forbids synchronous blocking disk I/O in the Tier 1 fast-path, yet Principle I.2 and spec §4 permit hook_runner to write telemetry to l1_staging_log. SQLite WAL permits exactly one writer; when the Memory Daemon holds the write lock, hook_runner's write blocks up to PRAGMA busy_timeout=5000ms, catastrophically exceeding the <25ms subprocess SLA and the <0.30ms reflex ceiling. The 'or' socket alternative is presented as optional, not mandatory, so the forbidden path remains reachable.
**Remediation**: `Forbid all SQLite writes from Process 1 (`hook_runner.py`). Telemetry MUST be delivered via non-blocking loopback socket to the Memory Daemon; if the daemon is unreachable, drop telemetry best-effort and return within <5ms. Make l1_staging_log exclusively daemon-owned and remove the write path from the hook. Add a fallback test that daemon-down invocations still complete under 25ms.`

### 3. [CRITICAL] VULN-003: S_0 contradiction and unclamped negative delta-t break S(t) ∈ [0,1] guarantee
**Description**: Constitution V.3 locks S_0=1.0, but spec 001 Scenario 3.3 uses S_0 ∈ [0.0,1.0], Scenario 3.4 uses S_0=0.15, and the DDL exposes a variable confidence_score. Pruning thresholds (S(t)<0.20 AND delta-t ≥ 7.0) therefore become non-deterministic, violating V.2 bounded-consolidation intent. Separately, the stability formula has no universal delta-t clamp: EC-005 clamps only in one path; a future last_accessed_at or clock skew yields delta-t<0, making the exponent positive, so exp(positive)>1 and S(t)>1.0 — a direct violation of the stated S(t)∈[0,1] invariant. Timestamp format/timezone is unvalidated.
**Remediation**: `Resolve S_0 semantics explicitly (if variable, delete the 'locked S_0=1.0' clause and define S_0 = confidence_score). Implement a single stability function with hard guard `delta_t = max(0.0, (now_utc - last_accessed_at).total_seconds()/86400.0)` and strict ISO-8601 UTC parsing (reject timezone-naive). Add property-based tests with future timestamps and non-monotonic clocks asserting S(t) ∈ [0,1].`

### 4. [CRITICAL] VULN-004: Dense-retrieval latency claims are physically impossible under the stdlib-only mandate
**Description**: Scenario 2.3 claims <0.50ms to score 1,000×384-dim cosine similarity (≈384,000 multiply-adds) and NFR-002 claims <15ms end-to-end across 10,000 records (≈3.84M multiplications plus 1536-byte blob unpacking per record). Pure-Python MACs run ~30–100ns/op, so 384K ops ≈12–38ms and 3.84M ops ≈120–380ms. NFR-004 mandates stdlib-only core with graceful BM25 fallback. The spec conflates a numpy/onnxruntime-backed fastembed path with the documented stdlib path.
**Remediation**: `Either (a) formally declare numpy as the single permitted optional binary with a pinned version and C-accelerated dot products, restating SLAs as achievable only in that mode, or (b) restrict dense scans to the workspace partition (bounded candidate cap, e.g., ≤500) and re-derive the latency budget from measured data. Remove the unqualified '10,000 records at <15ms' claim or split into lexical (<1ms, FTS5) and partitioned-dense budgets with explicit candidate limits.`

### 5. [HIGH] VULN-005: Basename fallback in target_file verification permits cross-workspace artifact confusion
**Description**: Scenario 2.1 accepts target_file matching by 'normalized path or basename'. Two workspaces each containing `spec.md` collide: a review generated for Workspace A's spec.md can pass Workspace B's gate. This breaches FR-013 workspace partition isolation and lets a stale/unscoped approval transit workspaces.
**Remediation**: `Require exact full canonical-path equality (`os.path.normcase(os.path.normpath(os.path.realpath(...)))`); remove basename-only matching entirely. Store workspace_hash in OMNI_AUDIT_META and require equality with the current workspace hash. Add a test with two distinct same-named files in separate workspaces.`

### 6. [HIGH] VULN-006: No hard client-side schema enforcement for --json mode; FLAW-001 floor unenforced
**Description**: FR-003 and EC-010 claim a 'schema validator rejects' responses that violate the floor, but no functional requirement mandates implementing Draft-07 validation inside consult_critic.py, and there is no regeneration loop. Since DeepSeek JSON mode performs no server-side Draft-07 validation (FLAW-001), a sycophantic `{"verdict":"APPROVED","critical_vulnerabilities":[]}` with fewer than 3 edge_cases is accepted verbatim. Anti-praise is only soft-prompted, so the echo chamber returns through the back door.
**Remediation**: `Add an FR requiring consult_critic.py to validate --json output against the embedded schema (hand-rolled stdlib validator), enforce the if/then floor locally (critical_vulnerabilities ≥ 3 when verdict ∈ {REJECTED, CONDITIONAL_PASS}; edge_cases ≥ 3 always), and on violation either downgrade the verdict or force one regeneration with a stricter system message before failing with exit code 1. Add an integration test injecting a schema-shaped sycophantic response.`

### 7. [HIGH] VULN-007: activation_events lacks workspace_hash; synchronous=NORMAL undermines permanent invariants
**Description**: activation_events stores only raw workspace_dir, forcing consolidation to derive workspace_hash — canonicalization drift across time and OS (normcase is identity on POSIX) can misclassify partitions and leak across workspaces, breaching FR-013/FR-014. Separately, a global PRAGMA synchronous=NORMAL in WAL can lose the most recently committed transactions on power loss; labeling records 'permanent invariants' under this durability level is a contradiction of Principle V.5. The DDL also has no drainer requirement linking l1_staging_log to activation_events.
**Remediation**: `Store the canonical workspace_hash at write time in activation_events (derived via canonical_workspace_hash) and add a test that path variants hash consistently. For invariant-class writes use synchronous=FULL plus a forced WAL checkpoint, or route invariants to an append-only durable segment. Add an explicit FR specifying the l1_staging_log → activation_events drainer as an owned single-writer responsibility.`

## 3. Concurrency, Race Condition & Mutex Hazards (5 identified)
- **Resource**: `omni_memory.db WAL single-writer lock` | **Hazard**: Writer contention with pre-flight hook (busy_timeout=5000ms) blocks the <25ms subprocess SLA when the daemon holds the lock | **Mitigation**: Remove L1 DB writes entirely; route telemetry via non-blocking loopback socket; keep l1_staging_log daemon-owned; assert latency with a fault-injected busy writer test.
- **Resource**: `llama_autostart.lock` | **Hazard**: TOCTOU between stale-mtime check and os.remove, plus a 30s stale threshold that overlaps the 12–20s cold start and 25s health-poll window, allowing lock theft and duplicate llama-server instances | **Mitigation**: Raise the stale threshold above max(cold-start + poll + margin); verify holder liveness via os.kill(pid, 0) with PID+start-time stored in the lock; require the holder to heartbeat-refresh lock mtime; use atomic rename-based takeover instead of remove-then-create.
- **Resource**: `MCP stdio JSON-RPC loop (deepseek_worker_mcp.py)` | **Hazard**: Single-threaded blocking 30s REST calls serialize concurrent tools/call requests and ignore cancellation/notification frames | **Mitigation**: Dispatch each tools/call to a bounded worker with a monotonic deadline; support notifications/cancelled; frame only JSON-RPC on stdout with all logs on stderr; specify newline-delimited framing and initialize capabilities/protocolVersion explicitly.
- **Resource**: `OMNI_GATEKEEPER_ACTIVE environment flag` | **Hazard**: Inherited into nested subprocess chains, blocking legitimate nested audits; unset paths allow re-entry recursion | **Mitigation**: Replace the coarse env flag with a per-invocation correlation/session id, an audit-depth counter, and an allowlist; ensure consult_critic.py never triggers hook_runner's gate path; log depth transitions.
- **Resource**: `WAL auto-checkpoint (wal_autocheckpoint=1000 pages)` | **Hazard**: Checkpoint flushing during heavy consolidation contends with readers and spikes L2 retrieval latency | **Mitigation**: Single-writer serialization plus checkpoint throttling during high-demand windows; monitor checkpoint duration; consider scheduled passive checkpoints outside interactive bursts.

## 4. Defensive Failure Scenarios & Edge Cases (7 verified)
### 1. Clock skew or a future last_accessed_at (t_now < t_last_accessed) flows into the unclamped stability formula
- **Consequence**: delta-t becomes negative, exp(-lambda*delta-t)>1, S(t)>1.0 — violates Principle V.2; a memory can be artificially immortalized or wrongly ranked
- **Mitigation**: Enforce `delta_t = max(0.0, ...)` inside the single decay entry point and validate ISO-8601 UTC timestamps (reject naive/future beyond a tolerance); add property tests asserting S(t) ∈ [0,1] under skew

### 2. Agent hand-writes a `<!-- OMNI_AUDIT_META: {"verdict":"APPROVED", ...} -->` header into CRITIC_REVIEW.md
- **Consequence**: Gatekeeper passes with zero external audit performed, defeating the entire tripartite separation of powers
- **Mitigation**: HMAC-signed artifacts with a key in DPAPI/Credential Manager; recompute and compare SHA-256(target) to meta.input_hash; fail closed on signature or hash mismatch

### 3. Architectural trigger phrase (e.g., 'create SDD spec.md') appears beyond character 2,048 of a long prompt
- **Consequence**: Principle I.3 head-clamping truncates the trigger before gatekeeper intent detection, producing a false-negative and an un-gated workflow
- **Mitigation**: Decouple gatekeeper intent scanning from the tokenization clamp: define a separate, still-bounded detection window (e.g., an independent cheap scan cap) and add a test with trigger after 2,048 chars of preamble

### 4. --file points to a path on a different Windows drive/mount than allowed_root
- **Consequence**: os.path.commonpath raises ValueError (mixed drives), producing an unhandled crash instead of exit code 4
- **Mitigation**: Wrap commonpath in try/except mapping to EXIT_CONFIG_ERROR (4); pre-validate same-drive/mount before commonpath; add test with cross-drive path

### 5. FTS5 MATCH operand concatenates a raw `:raw_q` value that contains boolean operators (AND, NOT, *) without sanitize_fts5_query applied
- **Consequence**: sqlite3.OperationalError is raised at query time, breaking the retrieval path
- **Mitigation**: Mandate sanitize_fts5_query at every MATCH call site (not just as an optional helper) and add a test with reserved punctuation/boolean strings asserting zero OperationalError

### 6. --json returns `{"verdict":"APPROVED","critical_vulnerabilities":[]}` with fewer than 3 edge_cases
- **Consequence**: Client accepts the sycophantic response, silently reinstating echo-chamber self-approval
- **Mitigation**: Client-side Draft-07 validation with an enforced if/then floor; on violation downgrade verdict or regenerate once, then exit code 1; add regression test

### 7. deepseek-v4.1-flash is rejected upstream (HTTP 400/404) and EC-014 silently falls back to deepseek-chat
- **Consequence**: A different model family/version produced the 'V4.1-Flash' audit while metadata may still claim the requested model, misrepresenting critical model identity
- **Mitigation**: Echo the actual API-reported model in the audit artifact and CriticResponse, print an explicit fallback notice, and record the fallback in AuditSession.model_version

## 5. Prescriptive Remediation Directives (10 items)
- Sign and verify every audit artifact with an HMAC bound to target canonical path, SHA-256 of target content, verdict, and review-body hash; store the key in DPAPI/Credential Manager; fail closed on mismatch.
- Remove ALL SQLite writes from hook_runner.py; deliver telemetry exclusively via non-blocking loopback socket and drop best-effort if the daemon is down; guarantee <25ms even under DB lock.
- Reconcile S_0 semantics across constitution/spec/DDL; enforce a single decay function with max(0.0, delta-t) clamping and strict ISO-8601 UTC validation; for invariants use synchronous=FULL or append-only durable storage.
- Replace stdlib-only latency claims with measured budgets; restrict dense scans to workspace partitions with a documented candidate cap; formally pin numpy as the sole optional binary (or restate SLAs as fastembed-mode-only).
- Delete basename fallback in target_file verification; require exact full canonical-path and workspace_hash equality; add cross-workspace collision tests.
- Add a hard client-side schema-validation FR for --json with local FLAW-001 floor enforcement and a single regeneration/downgrade loop; add sycophantic-response regression tests.
- Store canonical workspace_hash in activation_events at write time; add an FR specifying the l1_staging_log → activation_events drainer as a single-writer daemon responsibility.
- Unify the exit-code contract: resolve the 429-exhausted ambiguity (FR-004 says 3, FR-005 says 2) to a single deterministic mapping and test each branch.
- Fully specify MCP framing (newline-delimited JSON-RPC), initialize capabilities/protocolVersion, concurrency, and notifications/cancelled handling.
- Implement gatekeeper intent detection independently of the 2,048-char tokenization clamp and add a test with triggers located after 2,048 chars.

## 6. Council Gate Final Verdict: `REJECTED`
