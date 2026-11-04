<!-- OMNI_AUDIT_META: {"verdict":"APPROVED","target_file":"omni_kernel_v41_production_remediation.patch","input_hash":"sha256:c5fe9a36aa25690da250d0e3cc67383c4260770b5cbad3550074ad3ebfa8075b","model":"deepseek-flash","hash_domain":"raw_file_v1","hash_algo":"sha256-v2","timestamp_utc":"2026-11-04T19:03:53.779108+00:00","workspace_hash":"0f03e216b4ff8ec39315d4d9db720f619c14f85e5358e2aec11b48be314ab9eb","signature":"49200a44efeff59868c9e02c7b76c20e3ce83c51b4db7ca886b2e0432a717725"} -->

# 🛡️ Architectural Red-Teaming Audit: omni_kernel_v41_production_remediation.patch
**Audit Status**: `APPROVED` | **Model**: `deepseek-flash` | **Confidence**: `0.88` | **Timestamp**: `2026-11-04T19:03:53.779108+00:00`

## Executive Summary
Bản patch hardening rất lớn nhưng mạch lạc, được thiết kế cho môi trường cá nhân single-user. Các thay đổi chính (giới hạn kích thước đọc, cách ly workspace bằng SHA-256 + registry, migration tự động, khóa file advisory, outbox 2 pha, HMAC Council Gate, MemorySingleWriter có flush/close xác định) đều có đường xử lý lỗi rõ ràng và không phát hiện lỗi chức năng nào làm sập luồng sử dụng hàng ngày. Một vài thay đổi hành vi cần lưu ý (consolidator bắt buộc --workspace/--allow-unscoped, HMAC key phải được tạo bởi consult_critic trước khi gatekeeper xác thực) nhưng đều có fallback an toàn và hook_runner đã truyền --workspace đúng.

## 1. Constitutional & Ring 0 Invariants Verification
- ✅ Ring 0 Security (Zero-Trust SQL & Credential Redaction): PASS
- ✅ Principle I Reflex Latency Boundary: PASS
- ✅ Concurrency & Physical Resource Bounds: PASS

## 2. Top Critical Architectural Vulnerabilities (0 identified)
_No critical vulnerabilities identified. (Zero-defect floor verified)_

## 3. Concurrency, Race Condition & Mutex Hazards (5 identified)
- **Resource**: `proven_traces.json (.lock) & trust DB (.lock) via TrustFileLock/FileLock` | **Hazard**: OS advisory lock timeout / stale lock contention | **Mitigation**: Timeout có giới hạn + os.O_NOFOLLOW + kiểm tra st_nlink; OS tự nhả lock khi tiến trình chết. Trong dùng cá nhân, tranh chấp gần như không xảy ra và mọi lỗi đều trả False/raise có kiểm soát thay vì treo.
- **Resource**: `SQLite omni_memory.db (WAL)` | **Hazard**: BEGIN IMMEDIATE + SAVEPOINT lồng nhau giữa drain/consolidate/flush_outbox | **Mitigation**: own_tx được xác định bằng conn.in_transaction; flush_outbox từ chối chạy khi đang trong transaction ngoài; các thao tác file I/O (spool, record_trace) được đẩy ra ngoài transaction SQLite để tránh giữ write-lock lâu.
- **Resource**: `experiential_memory._CACHE/_MEM_LOCK` | **Hazard**: Đọc/ghi cache đồng thời giữa nhiều thread/process | **Mitigation**: RLock bảo vệ cache; cache key gồm (mtime_ns, size, ino) nên tự invalid khi file thay đổi ngoài tiến trình; recall trả deepcopy để tránh chia sẻ mutable state.
- **Resource**: `MemorySingleWriter queue + worker` | **Hazard**: Queue đầy/worker chết làm mất write | **Mitigation**: Queue có maxsize, enqueue_write có deadline/backpressure, flush()/close() có timeout và báo dropped task; _fatal_error lan truyền ra caller để fail-loud.
- **Resource**: `LifecycleGuard PID lock + heartbeat` | **Hazard**: Zombie reclaim / heartbeat clobbering | **Mitigation**: ProcessMutex + token + epoch CAS dưới mutex; heartbeat dừng khi mất quyền sở hữu; release chỉ unlink khi khớp cả pid và token.

## 4. Defensive Failure Scenarios & Edge Cases (7 verified)
### 1. consolidator.py được gọi thủ công không kèm --workspace và không có --allow-unscoped
- **Consequence**: Tiến trình thoát với mã 1 và thông báo LỖI VẬN HÀNH
- **Mitigation**: hook_runner tự động spawn consolidator với --workspace workspace_dir, nên luồng hook bình thường vẫn hoạt động; khi chạy tay chỉ cần thêm cờ.

### 2. proven_traces.json bị hỏng JSON
- **Consequence**: load_traces raise ValueError thay vì trả rỗng (tránh ghi đè mất dữ liệu cũ)
- **Mitigation**: record_trace bắt lỗi và trả {} (consolidator đánh dấu outbox thất bại, không crash); recall_traces dùng _get_traces_read_view có try/except trả [] và cảnh báo stderr.

### 3. DB cũ chứa workspace_hash 32-hex MD5 và dữ liệu trùng lặp trong l1_staging_log/activation_events
- **Consequence**: Migration có thể vi phạm UNIQUE index mới
- **Mitigation**: init_database chạy trong SAVEPOINT: gộp trùng trước khi tạo unique index, map 32-hex -> 64-hex qua workspace_registry nếu có path, giữ nguyên hash không map được; sau đó verify trigger/column và raise RuntimeError nếu thiếu.

### 4. Council Gate signing chưa từng tạo HMAC key (chưa chạy consult_critic)
- **Consequence**: verify_audit_meta fail-closed khi key thiếu (không tự provision trong verifier)
- **Mitigation**: verify_critic_artifact trả UNREVIEWED và hook vẫn xuất pre-flight bình thường; key được tạo khi consult_critic sinh review đầu tiên với auto_provision=True.

### 5. Crash giữa drain_l1_staging để lại file .proc_* mồ côi
- **Consequence**: Mất telemetry spool tạm thời
- **Mitigation**: Đầu mỗi drain quét và phục hồi .proc_* trở lại spool chính dưới TrustFileLock; spool chỉ bị xóa sau khi transaction SQLite commit thành công.

### 6. File lock rỗng trên Windows (msvcrt.locking cần >=1 byte)
- **Consequence**: msvcrt.locking có thể lỗi nếu file 0 byte
- **Mitigation**: Cả TrustFileLock và ProcessMutex đều ghi b'\x00' khi file rỗng trước khi khóa, và seek(0) trước mỗi lần lock.

### 7. Prompt inline được audit rồi thay đổi trước khi hook chạy
- **Consequence**: Gatekeeper có thể chấp nhận review cũ
- **Mitigation**: verify_critic_artifact bắt buộc user_prompt cho inline, so hash_prompt/sha256 raw; nếu lệch sẽ đánh dấu STALE_REVIEW.

## 5. Prescriptive Remediation Directives (6 items)
- Giữ thói quen luôn gọi consolidator qua hook hoặc kèm --workspace <dir>; nếu muốn quét toàn cục chủ động thêm --allow-unscoped.
- Chạy consult_critic ít nhất một lần trước khi dựa vào Gatekeeper verification để HMAC key được provision (~/.gemini/config/omni_audit.key).
- Khi nâng cấp DB cũ, nên sao lưu omni_memory.db trước lần chạy đầu tiên để migration SHA-256/MD5 diễn ra an toàn.
- Nếu thấy cảnh báo 'unconfigu red_unscoped_error' trong daemon, kiểm tra lại --workspace đã được truyền từ hook_runner chưa.
- Có thể kiểm tra nhanh lock tồn đọng bằng lifecycle_guard.py --cleanup-locks khi nghi có tiến trình chết giữ PID lock.
- Để sandbox thực thi test code tổng hợp (không chỉ AST), thêm cờ --allow-exec khi gọi synthesizer; mặc định là chỉ kiểm AST.

## 6. Council Gate Final Verdict: `APPROVED`
