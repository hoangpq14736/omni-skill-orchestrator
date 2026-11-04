<!-- OMNI_AUDIT_META: {"verdict":"CONDITIONAL_PASS","target_file":"omni_kernel_v41_production_remediation.patch","input_hash":"sha256:693e484ac9bbf8b507be88b9e87f5fc2da7b24d67bf3d4837a53b2456bc80f53","model":"deepseek-flash","hash_domain":"redacted_prompt_v1","hash_algo":"sha256-v2","timestamp_utc":"2026-11-04T16:26:38.918302+00:00","workspace_hash":"0f03e216b4ff8ec39315d4d9db720f619c14f85e5358e2aec11b48be314ab9eb","signature":"d8928ee19c0f280cb1e7085e28457a207930ee5d8322b6933ee5ef57eb601b4e"} -->

# 🛡️ Architectural Red-Teaming Audit: omni_kernel_v41_production_remediation.patch
**Audit Status**: `CONDITIONAL_PASS` | **Model**: `deepseek-flash` | **Confidence**: `0.72` | **Timestamp**: `2026-11-04T16:26:38.918302+00:00`

## Executive Summary
Massive hardening diff with strong improvements (transactional outbox, symlink containment, HMAC meta signing, bounded reads, type-confusion defense). However it is NOT 100% sound: silent exception swallowing persists in several ingestion paths, the new run_repo_audit.py has an undeclared dependency and unbounded file reads, the traces cache relies on mtime-only coherency which is unsafe on coarse-timestamp FS, and MemorySingleWriter close/flush accounting is unreliable. Merge only after the P0/P1 fixes below.

## 1. Constitutional & Ring 0 Invariants Verification
- ⚠️ Gatekeeper Finding: Invariant check issued verdict `CONDITIONAL_PASS` with 5 vulnerability findings.

## 2. Top Critical Architectural Vulnerabilities (5 identified)
### 1. [HIGH] VULN-001: Silent exception swallowing persists in assimilator.py workspace ingestion
**Description**: find_workspace_skills() and find_workspace_rules() still wrap the per-file read/scan/persist logic in a bare `except Exception: pass`. A malformed, oversized, or partially-readable SKILL.md / rule file is dropped with zero diagnostic output at default verbosity, so the user silently loses an entire rule/skill without knowing. This directly violates the stated 'fail loudly with diagnostic context; never silently swallow unexpected exceptions' invariant and can mask an attacker deliberately corrupting one rule so the guard never sees it.
**Remediation**: `Replace `except Exception: pass` with `except Exception as e: sys.stderr.write(persist_diag(e))` and record the path via a bounded `blocked_list`/skipped-list entry so the CLI can surface exactly which files were skipped and why.`

### 2. [HIGH] VULN-002: run_repo_audit.py has undeclared import and unbounded file reads (OOM + DoA)
**Description**: The new script `from sanitizer import redact_credentials` is not part of this diff; if sanitizer.py is absent, the module raises ImportError at import time and the whole audit runner is dead-on-arrival. Additionally bundle_cluster_files() does `fp.read()` with no size cap on arbitrary repository files, so a single multi-hundred-MB artifact (or a maliciously huge file) OOMs the auditor. Neither is caught before the expensive API loop starts.
**Remediation**: `Declare/verify the sanitizer dependency or replace with `memory_utils.redact_secrets`; cap file reads via `os.path.getsize <= MAX_SKILL_SIZE` (matching indexer.py) and read `fp.read(MAX)`; wrap the whole module import in a startup self-check that exits with a clear diagnostic.`

### 3. [MEDIUM] VULN-003: mtime-only cache coherency in experiential_memory.load_traces enables stale reads / lost updates
**Description**: load_traces caches strictly by `os.path.getmtime(abs_path)`. On coarse-granularity filesystems (FAT/exFAT, many SMB/CIFS mounts) two writes within the same 1–2s window produce identical mtime, so a second process returns a stale in-memory cache. Worse, record_trace does `load_traces(path)` inside FileLock and then `_save_traces_unlocked(data)`, so a reader that started with stale cache can write back the stale snapshot, clobbering the concurrent atomic os.replace performed by the consolidator.
**Remediation**: `Use a stronger cache key: (st_mtime_ns, st_size, st_ino) tuple, or drop the mtime cache for the write path entirely and always re-read inside the lock; treat a size/mtime mismatch as a miss. Consider fsync-ing the cache key update in record_trace after replace.`

### 4. [MEDIUM] VULN-004: MemorySingleWriter.close()/flush() accounting is unreliable
**Description**: close() returns `self._queue.unfinished_tasks` as the 'dropped' count, which includes the sentinel None task and therefore overcounts; if the worker fails to terminate within timeout the code only sets `_fatal_error` and logs a warning without raising, so a caller (or process) can believe all writes were durably flushed while they were silently lost. flush() also resets `_evicted_failures_count` to zero after raising once, so a second flush() will not re-report prior evicted failures.
**Remediation**: `Track drained vs dropped counts explicitly; make close() raise or return a structured result `{dropped: N, timed_out: bool}`; persist the evicted-failure summary until a successful flush acknowledgement; never reset counters before the caller has observed them.`

### 5. [MEDIUM] VULN-005: consult_critic.py misaligned indentation in JSON-repair failure branch is fragile
**Description**: Inside execute_critic_request the repair-failure handler places `if os.environ.get('CRITIC_DEBUG') == '1':` at a deeper indentation than the parent `except json.JSONDecodeError as jde:` block. It currently parses only because the comment above it is ignored, but any editor/formatting pass that touches this region yields IndentationError, which breaks import of consult_critic and, transitively, run_repo_audit. This is a latent single point of failure for the whole auditing pipeline.
**Remediation**: `Normalize the block to a single consistent indent level and add a static syntax check (python -m py_compile) to CI/pre-commit so mis-alignment cannot merge.`

## 3. Concurrency, Race Condition & Mutex Hazards (4 identified)
- **Resource**: `Companion *.lock / *.mutex lock files (TrustFileLock, ProcessMutex)` | **Hazard**: Windows LockFile region on a 0-byte file; inconsistency between FileLock (pre-sizes 1 byte) and TrustFileLock/ProcessMutex (do not pre-size) | **Mitigation**: Always open O_CREAT|O_RDWR, write a single 0x00 byte via os.write + os.fsync if size==0, then os.lseek(0) before msvcrt.locking/flock.
- **Resource**: `proven_traces.json in-memory _CACHE` | **Hazard**: Cross-process lost update when two processes read stale cache then write under local lock | **Mitigation**: Re-read from disk inside the FileLock critical section (never trust the process-local cache on the write path); key cache by (mtime_ns, size, inode).
- **Resource**: `consolidation_outbox InFlight claim lease (180s)` | **Hazard**: A hung or extremely slow record_trace(file I/O) causes a second worker to reclaim the row while the first is still writing, producing concurrent file writes | **Mitigation**: FileLock already serializes the file write, but the reclaim could still double-process; keep generation CAS (already present) and consider heartbeat refresh of the InFlight claim during long I/O, or lower the lease only when a liveness probe of the owner token fails.
- **Resource**: `MemorySingleWriter queue + flush() condition variable` | **Hazard**: close() racing enqueue_write() and flush() while worker drains; unreliable dropped count | **Mitigation**: Guard close()/flush() with a single mutex, make enqueue fail-fast on close, and return an explicit structured drain report.

## 4. Defensive Failure Scenarios & Edge Cases (4 verified)
### 1. Workspace path is a Windows junction / reparse point (not detected by os.path.islink)
- **Consequence**: assimilator.is_safe_workspace_file skips the islink rejection, but the subsequent realpath containment check may still prevent escape; indexer._parse_skill_file only checks os.path.islink and could follow a junction whose realpath differs.
- **Mitigation**: Route all containment through a single helper using os.path.realpath + st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT checks on Windows, and compare commonpath against the realpath root; never rely on os.path.islink alone.

### 2. User prompt is itself a JSON object/array (e.g., pasted payload) passed to redact_secrets
- **Consequence**: redact_secrets parses and re-serializes the string, altering whitespace/number formatting before it is hashed for the Council Gate input_hash, so produce/verify can disagree if one path redacts and the other does not.
- **Mitigation**: Define hash_domain explicitly (redacted_prompt_v1) and ensure both signing (consult_critic) and verification (hook_runner) hash the *same* post-redaction byte string deterministically; add a regression test with a JSON-looking prompt.

### 3. sanitize_unicode_skeleton is applied to non-Latin rule content (Devanagari, Thai, CJK with combining marks)
- **Consequence**: NFD + combining-mark stripping + confusable transliteration can silently alter semantic characters before injection scanning, causing false negatives for non-EN/VI bypasses and/or corrupting characters in the scanned view.
- **Mitigation**: Use the skeleton only for matching, keep the original bytes for storage/display; scope combining-mark stripping to Latin script blocks used in the EN/VI patterns; add unit tests for Thai/Devanagari/CJK inputs to confirm no false corruption.

### 4. Legacy consolidation_outbox rows with generation = NULL or l1_staging_log with NULL last_error
- **Consequence**: COALESCE(generation,1) handles reads, but the ON CONFLICT DO UPDATE increments `generation = consolidation_outbox.generation + 1`, which evaluates to NULL if a legacy row had NULL generation, disabling the CAS fencing.
- **Mitigation**: Backfill `UPDATE ... SET generation = 1 WHERE generation IS NULL` during migration, and use `COALESCE(consolidation_outbox.generation, 1) + 1` in the upsert.

## 5. Prescriptive Remediation Directives (8 items)
- Replace every remaining `except Exception: pass` in assimilator.py (and audit all consolidation rollback paths) with `persist_diag(e)` + stderr, and record skipped files so the CLI reports them.
- Add explicit size bounds to run_repo_audit.bundle_cluster_files and resolve/verify the `sanitizer.redact_credentials` dependency at import time with a clear exit code.
- Harden the traces cache to a (mtime_ns, size, inode) key and force a disk re-read for the write path in record_trace.
- Make MemorySingleWriter.close() return a structured drain report and never claim success when a flush timed out or evicted failures remain unseen.
- Normalize the consult_critic.py repair-branch indentation and add py_compile to the pre-merge gate.
- Unify lock-file creation across FileLock/TrustFileLock/ProcessMutex: pre-size 1 byte + seek(0) + O_NOFOLLOW + non-regular-file rejection on Windows and POSIX.
- Backfill consolidation_outbox.generation for legacy rows and wrap the upsert increment in COALESCE to preserve CAS fencing.
- Keep the excellent transactional outbox/generation-CAS and HMAC fail-closed verifier patterns; add targeted unit tests for lost-update, stale-mtime, and junction/symlink escape before merging.

## 6. Council Gate Final Verdict: `CONDITIONAL_PASS`
