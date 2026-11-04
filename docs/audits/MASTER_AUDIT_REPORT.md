# 🛡️ Omni-Kernel v4.1: Repository Master Architectural Audit
**Date:** 2026-11-04 03:35:57 UTC | **Auditor Model:** `deepseek-flash` | **Total Elapsed:** 418.9s

## Executive Summary Table
| Cluster | Verdict | Confidence | Vulnerabilities | Concurrency Hazards | Report Artifact |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Cluster 1: Memory Engine, Concurrency & SQLite WAL** | `REJECTED` | 0.97 | 10 | 6 | [cluster_1_memory_concurrency.md](./cluster_1_memory_concurrency.md) |
| **Cluster 2: Pre-Flight Hook, Latency & IPI Sanitizer** | `REJECTED` | 0.94 | 9 | 6 | [cluster_2_preflight_hook_latency.md](./cluster_2_preflight_hook_latency.md) |
| **Cluster 3: Resolver, Arbitration, Dynamic Bus & Indexer** | `REJECTED` | 0.94 | 9 | 5 | [cluster_3_resolver_arbitration_bus.md](./cluster_3_resolver_arbitration_bus.md) |
| **Cluster 4: Specifications & SDD Blueprints** | `REJECTED` | 0.93 | 7 | 5 | [cluster_4_specs_sdd_blueprints.md](./cluster_4_specs_sdd_blueprints.md) |
| **Cluster 5: Core Contracts, Testing & System Invariants** | `REJECTED` | 0.92 | 9 | 5 | [cluster_5_contracts_tests_invariants.md](./cluster_5_contracts_tests_invariants.md) |

**Total Vulnerabilities Identified:** 44 | **Total Concurrency Hazards:** 27

## Consolidated Actionable Remediation Plan

### Cluster 1: Memory Engine, Concurrency & SQLite WAL
- [ ] Fix workspace isolation first: add workspace_hash filtering to final hydration, preserve workspace_hash without rehashing, and cluster promotions by (workspace_hash, normalized_signature).
- [ ] Replace direct SQLite writes in revert_invariant and consolidator with the single-writer contract, or enforce a strict transaction API that checks conn.in_transaction and rolls back before BEGIN.
- [ ] Enable PRAGMA foreign_keys=ON and PRAGMA recursive_triggers=ON on every connection that writes workspace_episodic_memory or dense_embeddings, and add integrity checks for orphan embeddings and FTS row counts.
- [ ] Remove broad except/pass blocks around backfill, vacuum, checkpoint, callbacks, and vector corruption. Emit structured diagnostics with memory_id, workspace_hash, model_name, and exception text, then rollback or fail the batch.
- [ ] Validate all numeric and temporal inputs: embedding dimensions, finite norms, ISO-8601 timestamps, non-negative activation counts, and bounded limit values.
- [ ] Do not concatenate raw sanitized strings into FTS5 MATCH expressions. Tokenize and validate the query, reject empty or unsafe expressions, and wrap execution errors with query context.
- [ ] Promote traces only on positive feedback evidence, not neutral 0.0 feedback, and record the exact event IDs used for promotion.
- [ ] Add targeted tests for MemorySingleWriter worker death, revert_invariant transaction nesting, cross-workspace dense leakage, FTS REPLACE behavior, malformed timestamps, and duplicate consolidator acquisition. The existing WAL stress test does not exercise these failure paths.

### Cluster 2: Pre-Flight Hook, Latency & IPI Sanitizer
- [ ] Do not merge this cluster until all CRITICAL findings are fixed and regression-tested.
- [ ] Fix all Win32 ctypes bindings with explicit restype and argtypes, especially OpenProcess, WaitForSingleObject, GetExitCodeProcess, and CloseHandle.
- [ ] Make every lockfile, trust DB, telemetry file, and skill write atomic via temp file, fsync, and os.replace; add cross-process file locking.
- [ ] Replace unsigned review artifacts with signed or HMAC-authenticated metadata and exact canonical target path binding. Require target existence and input_hash.
- [ ] Sanitize and allowlist every workspace-derived string before injecting it into ephemeralMessage; strip control characters, newlines, markdown fences, and oversized fields.
- [ ] Move SQLite staging and telemetry off the synchronous pre-flight path or enable WAL with a short busy timeout; remove bare except Exception: pass from security and data-integrity paths.
- [ ] Fix Git safety detection to locate the repository root and handle .git worktree files; create missing parent directories before atomic writes.
- [ ] Add credential redaction and restrictive file permissions for persisted prompts and activation history.
- [ ] Add adversarial tests for IPI bypass, forged OMNI_AUDIT_META, stale review TOCTOU, PID reuse, permission-denied liveness, concurrent lock acquisition, and Windows 64-bit handle behavior.
- [ ] Instrument end-to-end hook latency with p95/p99 metrics and fail open only with explicit, durable diagnostic logging.

### Cluster 3: Resolver, Arbitration, Dynamic Bus & Indexer
- [ ] Remove automatic execution of synthesized test code or replace it with a real OS sandbox and explicit human approval.
- [ ] Serialize skill frontmatter with a safe encoder and reject newlines/control characters in description before writing SKILL.md.
- [ ] Add hard size, token-count, token-length, and registry-size limits across indexer.py, resolver.py, and mcp_gateway.py.
- [ ] Treat MCP JSON schemas as untrusted: validate root fields, property types, required lists, and reject malformed tools before indexing or routing.
- [ ] Implement recursive MCP argument validation with additionalProperties=false, enum/format checks, and bool-before-int type discrimination.
- [ ] Replace arbitration with a total deterministic ordering and re-sort selected candidates after every replacement before top_k slicing.
- [ ] Make registry.json and learned_affinities.json writes atomic with temp files, fsync, os.replace(), unique temp names, and advisory locks.
- [ ] Use follow_symlinks=False and realpath containment checks for every workspace scan; reject symlinked skill/rule paths.
- [ ] Require explicit MCP manifests and exclude plugin.json/metadata JSON from tool indexing; gate workspace MCP configs behind trust approval.
- [ ] Replace broad except Exception: pass blocks with fail-loud diagnostics that include path, operation, and exception class; add fuzz tests for malformed JSON, oversized inputs, tied scores, and concurrent writers.

### Cluster 4: Specifications & SDD Blueprints
- [ ] Sign and verify every audit artifact with an HMAC bound to target canonical path, SHA-256 of target content, verdict, and review-body hash; store the key in DPAPI/Credential Manager; fail closed on mismatch.
- [ ] Remove ALL SQLite writes from hook_runner.py; deliver telemetry exclusively via non-blocking loopback socket and drop best-effort if the daemon is down; guarantee <25ms even under DB lock.
- [ ] Reconcile S_0 semantics across constitution/spec/DDL; enforce a single decay function with max(0.0, delta-t) clamping and strict ISO-8601 UTC validation; for invariants use synchronous=FULL or append-only durable storage.
- [ ] Replace stdlib-only latency claims with measured budgets; restrict dense scans to workspace partitions with a documented candidate cap; formally pin numpy as the sole optional binary (or restate SLAs as fastembed-mode-only).
- [ ] Delete basename fallback in target_file verification; require exact full canonical-path and workspace_hash equality; add cross-workspace collision tests.
- [ ] Add a hard client-side schema-validation FR for --json with local FLAW-001 floor enforcement and a single regeneration/downgrade loop; add sycophantic-response regression tests.
- [ ] Store canonical workspace_hash in activation_events at write time; add an FR specifying the l1_staging_log → activation_events drainer as a single-writer daemon responsibility.
- [ ] Unify the exit-code contract: resolve the 429-exhausted ambiguity (FR-004 says 3, FR-005 says 2) to a single deterministic mapping and test each branch.
- [ ] Fully specify MCP framing (newline-delimited JSON-RPC), initialize capabilities/protocolVersion, concurrency, and notifications/cancelled handling.
- [ ] Implement gatekeeper intent detection independently of the 2,048-char tokenization clamp and add a test with triggers located after 2,048 chars.

### Cluster 5: Core Contracts, Testing & System Invariants
- [ ] Xóa fallback `redact_credentials` permissive; sanitizer thiếu = hard exit 5 + thông điệp 'LỖI BẢO MẬT'. Thêm test CI với fixture `sk-`/`postgres://user:pass@` chứng minh elision thực sự xảy ra.
- [ ] Áp dụng `validate_path`/allowed-root cho CẢ `--file` và `--out`; dùng `os.open(O_NOFOLLOW)` + `fstat` + `realpath('/proc/self/fd/N')`; `mkstemp` + `fsync` + `chmod 0o600` + `finally: unlink`.
- [ ] Reject mọi `api_base` không phải `https` (qua `urlsplit`, có host allowlist tuỳ chọn) với exit 4; đặt `check_hostname=True` và `CERT_REQUIRED` tường minh.
- [ ] Cap `resp.read` ở 2MB, đọc theo chunk, kiểm tra `Content-Length`, và enforce deadline monotonic tích lũy bên trong vòng đọc — không chỉ `socket_timeout` per-op.
- [ ] Validator phải type-check từng field (confidence_score float ∈ [0,1], mỗi list item là dict với schema con, `id` khớp regex). Vi phạm → exit 5. Bọc `format_markdown_report` trong try/except → exit 5 có context, không bao giờ để traceback thô thoát mã 1.
- [ ] Thay toàn bộ `except Exception: pass` bằng ghi stderr kèm `type(e).__name__`, thông điệp, và đường dẫn/ngữ cảnh liên quan. Chỉ giữ pass cho `UnicodeEncodeError` khi reconfigure stream.
- [ ] Hợp nhất Ring 0 invariants về một block duy nhất trong `rules/__kernel_invariants.md`; sinh `GEMINI.md`/`.cursorrules`/`AGENTS.md` bằng `updater.py --sync-kernel`; CI fail khi hash lệch; test khẳng định đúng 1 cặp marker/file và đủ 7 điều.
- [ ] Đặt `MIN_TIMEOUT = MIN_INFER_WINDOW + 1.0`; từ chối `--timeout` ngoài biên bằng exit 4 thay vì clamp im lặng.
- [ ] Tách kênh: `--json` → chỉ JSON trên stdout, mọi thông điệp người đọc → stderr.
- [ ] Đưa `dual_tier.py` vào bundle hoặc `importorskip` có lý do rõ ràng; chuyển assertion độ trễ <0.1ms ra khỏi unit-test gate sang benchmark trung vị nhiều lượt.
- [ ] Sửa conditional contract: `CONDITIONAL_PASS` không được mang finding `CRITICAL`; bỏ sàn cứng >=3 cho mọi verdict không-APPROVED, thay bằng yêu cầu `remediation` non-empty từng mục — tránh bịa finding để thỏa schema.
- [ ] Loại bỏ các đường dẫn tuyệt đối hardcode `C:/Users/vuhuu/...` khỏi `rules/AGENTS.md`; thay bằng biến môi trường/tương đối hoá `$OMNI_HOME` để tránh lộ PII và tăng tính di động.
- [ ] Thêm advisory lock (`fcntl.flock`) trên `<out>.lock` khi ghi artifact; consumer phải verify `input_hash` + HMAC của `OMNI_AUDIT_META` trước khi tin `verdict`.