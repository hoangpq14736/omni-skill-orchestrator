<!-- OMNI_AUDIT_META: {"verdict":"APPROVED","target_file":"dsh_auditor.py","input_hash":"sha256:4feab703962ab1bf4dfd68fb9a3bdc2d9cd9891b58fd89af9d0a376d6d6dda08","model":"deepseek-flash","hash_domain":"raw_file_v1","hash_algo":"sha256-v2","timestamp_utc":"2026-11-12T19:22:27.018966+00:00","workspace_hash":"7845dcbea5badfa6ac16e154c2d7f2d5e46ce980a48500b822090dc90650930a","signature":"bfe6148bcc57a955468546ad235d0c79994e96de5b12698018289bdf353f347f"} -->

# 🛡️ Architectural Red-Teaming Audit: dsh_auditor.py
**Audit Status**: `APPROVED` | **Model**: `deepseek-flash` | **Confidence**: `0.86` | **Timestamp**: `2026-11-12T19:22:27.018966+00:00`

## Executive Summary
Đã rà soát toàn bộ orchestrator (LockManager, ProvenanceLedger, DynamicWorkspaceResolver, NDJSON parser, streaming executor). Không phát hiện lỗi chức năng nào gây crash trong luồng sử dụng cá nhân hằng ngày: lock đa tiến trình có heartbeat + reclaim theo nonce, rollback mutation có backup dirty files, teardown 3 tầng đều có retry và deferred cleanup, retry session hết hạn được xử lý, quoting .cmd trên Windows có xử lý đúng. Code chạy được, logic nhất quán, đủ điều kiện APPROVED.

## 1. Constitutional & Ring 0 Invariants Verification
- ✅ Ring 0 Security (Zero-Trust SQL & Credential Redaction): PASS
- ✅ Principle I Reflex Latency Boundary: PASS
- ✅ Concurrency & Physical Resource Bounds: PASS

## 2. Top Critical Architectural Vulnerabilities (0 identified)
_No critical vulnerabilities identified. (Zero-defect floor verified)_

## 3. Concurrency, Race Condition & Mutex Hazards (3 identified)
- **Resource**: `.dsh_audit.lock (file lock trong repo root)` | **Hazard**: Race hiếm giữa heartbeat rewrite (os.replace) và reclaim của tiến trình khác nếu heartbeat trễ quá timeout_sec | **Mitigation**: Heartbeat interval = min(max(timeout/4, 1), 5) nên luôn nhỏ hơn nhiều so với timeout; reclaim có kiểm tra nonce trước khi xóa, nếu nonce lệch thì os.replace khôi phục lại lock cũ. Với single-user, rủi ro thực tế gần như bằng 0.
- **Resource**: `git index.lock` | **Hazard**: ensure_git_index_unlocked() trên POSIX xóa index.lock cũ >30s mà không kiểm tra có tiến trình git đang chạy | **Mitigation**: Chỉ xóa khi file đã cũ >30s; trên Windows có kiểm tra tasklist git.exe. Nếu gặp git add lớn chạy >30s trên Linux/macOS thì nên bổ sung kiểm tra pgrep git trước khi unlink (xem prescriptive_directives).
- **Resource**: `Process tree của DSH khi timeout` | **Hazard**: Trên POSIX, terminate_process_tree chỉ os.kill(pid, 9) tiến trình cha, không kill con | **Mitigation**: Con còn sống sẽ giữ sandbox → purge thất bại → ghi vào .deferred_cleanups.txt và sweep_deferred_cleanups() dọn ở lần chạy sau. Không treo CLI trên Windows (taskkill /F /T).

## 4. Defensive Failure Scenarios & Edge Cases (7 verified)
### 1. Lockfile mồ côi do lần chạy trước bị crash (PID đã chết, heartbeat cũ)
- **Consequence**: Nếu không xử lý, mọi audit sau sẽ báo LOCK_CONTENTION_TIMEOUT
- **Mitigation**: _handle_existing_lock() kiểm tra is_process_alive(pid) và delta heartbeat > timeout_sec, sau đó _attempt_stale_reclaim() rename lock sang file .reclaim, xác minh nonce rồi xóa. Lockfile 0-byte cũ >5s cũng được purge riêng.

### 2. Người dùng resume một --session-id đã hết hạn hoặc không tồn tại trên DSH
- **Consequence**: DSH trả error 'unknown session' và không có kết quả audit
- **Mitigation**: Parser bắt error event + heuristic stderr, sau đó retry đúng một lần với --session-id bị bỏ (fresh Turn 1) và dùng parser mới; session_id thực tế lấy lại từ event 'session'/'final'.

### 3. DSH in ra stdout các dòng không phải JSON (log nhiễu, banner, cảnh báo)
- **Consequence**: Parser có thể ném exception và làm hỏng toàn bộ stream
- **Mitigation**: feed_line() bắt json.JSONDecodeError, ghi warning EC-007 ra stderr và bỏ qua dòng đó; vòng đọc stdout còn bọc try/except quanh từng lần feed_line.

### 4. DSH ghi/sửa/xóa file ngoài target_paths ở Tier 1 hoặc Tier 2
- **Consequence**: Workspace bị biến dạng ngoài ý muốn của người dùng
- **Mitigation**: So sánh snapshot trước/sau (sha256 + mtime cache), file CREATED bị xóa, file MODIFY/DELETE được khôi phục từ rollback_backups hoặc git checkout HEAD; kết quả bị đánh success=False và ghi provenance ledger.

### 5. Đường dẫn cài DSH là file .cmd và repo root có dấu cách (--add-dir "C:\My Repo")
- **Consequence**: cmd.exe có thể strip nhầm dấu nháy khiến tham số bị tách sai
- **Mitigation**: Dùng wrapper cmd.exe /d /s /c "<list2cmdline>" để chỉ strip lớp nháy ngoài cùng, giữ nguyên quoting bên trong; nhánh này chỉ kích hoạt với .cmd/.bat trên Windows.

### 6. Repo có file dirty rất lớn (>10MB) chưa commit trước khi audit Tier 1/2
- **Consequence**: Backup có thể treo lâu hoặc phình scratch
- **Mitigation**: backup_dirty_files() bỏ qua file vượt max_bytes kèm cảnh báo; rollback khi đó fallback sang git checkout HEAD thay vì copy backup.

### 7. Teardown sandbox/worktree thất bại vì file còn bị khóa (antivirus, process con)
- **Consequence**: Rác tích lũy trong scratch
- **Mitigation**: purge_directory_robust() retry 4 lần với backoff + reset thuộc tính read-only; nếu vẫn thất bại thì ghi entry vào .deferred_cleanups.txt và sweep_deferred_cleanups() dọn đầu lần chạy kế tiếp (có kill zombie >1h).

## 5. Prescriptive Remediation Directives (5 items)
- Bổ sung kiểm tra tiến trình git đang chạy trên POSIX trước khi unlink index.lock trong ensure_git_index_unlocked() (dùng pgrep -x git) để tránh xóa lock của một git add lớn đang chạy.
- ProvenanceLedger.take_snapshot() hash toàn bộ file không giới hạn kích thước; nên thêm ngưỡng max_bytes (ví dụ 5-10MB) hoặc bỏ qua file binary lớn để giảm độ trễ snapshot ở Tier 1/2.
- Trên POSIX, nên chạy DSH với start_new_session=True và kill toàn bộ process group (os.killpg) trong terminate_process_tree để timeout thực sự dừng cả cây tiến trình và giảm phụ thuộc vào deferred cleanup.
- Thêm coverage.xml, junit*.xml, test-results/ vào IGNORE_FILES/IGNORE_DIRS để audit TEST_EXISTING ở Tier 1 không bị false-positive VIOLATION khi test suite sinh report.
- Khi final event có text rỗng nhưng có text_chunks, nên fallback sang '\n'.join(text_chunks) thay vì trả chuỗi rỗng để không mất verdict_text.

## 6. Council Gate Final Verdict: `APPROVED`
