<!-- OMNI_AUDIT_META: {"verdict":"CONDITIONAL_PASS","target_file":"cluster1_remediation.patch","input_hash":"sha256:0b0e775947b09c0dbb4583ce23372d3df0458a01ac4558e77a81278626298f6d","model":"deepseek-flash","timestamp_utc":"2026-11-04T11:47:20.593622+00:00"} -->

# 🛡️ Architectural Red-Teaming Audit: cluster1_remediation.patch
**Audit Status**: `CONDITIONAL_PASS` | **Model**: `deepseek-flash` | **Confidence**: `0.63` | **Timestamp**: `2026-11-04T11:47:20.593622+00:00`

## Executive Summary
Bản diff đã parameter hóa toàn bộ SQL (không phát hiện SQL injection), thêm CAS/lease, generation fencing, redaction theo key-structure và workspace isolation — hướng đúng. Tuy nhiên còn nhiều lỗi độ bền vững: đệ quy không giới hạn trong phân loại lỗi I/O, nuốt lỗi im lặng ở nhiều chỗ, eviction làm mất dấu write-failure (silent data loss), thay đổi ngữ nghĩa canonical_workspace_hash không có migration, và mẫu regex private-key có thể super-linear trên payload lớn. NOT merge-ready cho tới khi các directive được xử lý. Verdict: CONDITIONAL_PASS.

## 1. Constitutional & Ring 0 Invariants Verification
- ⚠️ Gatekeeper Finding: Invariant check issued verdict `CONDITIONAL_PASS` with 7 vulnerability findings.

## 2. Top Critical Architectural Vulnerabilities (7 identified)
### 1. [HIGH] VULN-001: Đệ quy vô hạn trong is_transient_io_error qua __cause__ (DoS)
**Description**: is_transient_io_error() đệ quy theo err.__cause__ mà không có visited-set. Python cho phép tạo chu trình (ví dụ `raise e from e` đặt e.__cause__ = e, hoặc chuỗi cause vòng tròn do wrapper exception library). Khi flush_outbox/consolidate_batch gặp một exception như vậy sẽ đệ quy vô hạn → RecursionError/stack exhaustion, làm sập worker và treo pipeline consolidation. Đây là vector DoS từ dữ liệu lỗi do bên ngoài kiểm soát (payload độc hại kích hoạt lỗi rồi bọc bằng `from`).
**Remediation**: `Thêm `seen: set` các id() của exception trong is_transient_io_error; trả False khi gặp lại. Đồng thời giới hạn độ sâu (ví dụ max 16). Cân nhắc kiểm tra cả __context__.`

### 2. [HIGH] VULN-002: Eviction của _failed_sequences có thể nuốt lỗi ghi (silent write failure)
**Description**: MemorySingleWriter giới hạn _failed_sequences còn 256 phần tử, loại bỏ key nhỏ nhất (min). Nếu >256 task fail trước khi flush() được gọi, các failure cũ bị xóa khỏi map; flush() sau đó chỉ kiểm tra `s <= target_seq` trên phần còn lại → nó trả về THÀNH CÔNG dù đã có ghi thất bại. Điều này vi phạm trực tiếp nguyên tắc 'no silently swallowed exceptions' và gây mất dữ liệu im lặng (caller tưởng đã commit).
**Remediation**: `Không bao giờ loại bỏ failure chưa được báo cáo. Giữ cờ `dropped_failures_since_flush`; flush() phải raise nếu cờ này bật. Hoặc lưu failure vào dead-letter bền vững thay vì đếm trong bộ nhớ. close() hiện chỉ cảnh báo khi dropped>0 — nên raise/trả trạng thái lỗi rõ ràng.`

### 3. [HIGH] VULN-003: Thay đổi canonical_workspace_hash (realpath+NFC) không có migration → mất ánh xạ tenant
**Description**: Hàm chuyển từ normcase(normpath(abspath)) sang unicodedata.NFC + normcase(realpath(abspath)). Với mọi đường dẫn chứa symlink/junction hoặc khác biệt Unicode NFC/NFD, hash sinh ra KHÁC hoàn toàn hash cũ. Các bản ghi workspace_episodic_memory / workspace_registry hiện có (khóa bằng hash cũ) sẽ không còn khớp hash mới → dữ liệu tenant trở nên vô hình, kiểm tra containment authorized_hashes sai, có thể dẫn tới từ chối/hoạt động nhầm và rò rỉ logic giữa phiên bản cũ/mới. Đây là data-integrity + isolation hazard nghiêm trọng khi nâng cấp in-place.
**Remediation**: `Cung cấp bước migration re-key: đọc workspace_path từ registry, tính lại hash mới, cập nhật hàng loạt trong transaction; hỗ trợ dual-read (chấp nhận cả 64-hex hash cũ) trong giai đoạn chuyển tiếp. Ghi rõ trong release notes và thêm test cho symlink + NFD.`

### 4. [MEDIUM] VULN-004: Nuốt lỗi im lặng (except Exception: pass) trong khởi tạo authorization
**Description**: ConsolidatorEngine.__init__ bọc truy vấn workspace_registry và các phép canonicalize trong `except Exception: pass`. Nếu DB/registry lỗi hoặc schema chưa tồn tại, authorized_hashes khởi tạo không đầy đủ mà KHÔNG có cảnh báo, khiến các kiểm tra isolation sau đó dùng tập authorized thiếu → có thể từ chối nhầm hoặc (nếu kết hợp allow_unscoped) chấp nhận đường dẫn ngoài phạm vi. Vi phạm 'fail loudly with diagnostic context'.
**Remediation**: `Thay mọi `except Exception: pass` mang tính logic bằng log có ngữ cảnh + cờ trạng thái degraded (ví dụ self.authorization_incomplete=True) và từ chối các thao tác scoped khi cờ bật. Chỉ nuốt lỗi ở cleanup thuần (close fd/rlock) mới hợp lý.`

### 5. [MEDIUM] VULN-005: Regex private-key có thể super-linear (ReDoS) trên payload 256KB
**Description**: Mẫu `-----BEGIN [A-Z ]+ PRIVATE KEY-----(?:(?!-----BEGIN)[\s\S])*?-----END ...` kết hợp định lượng tham lam `[A-Z ]+` và quét lazy toàn chuỗi trên input tới 262144 ký tự (redact_secrets chỉ cắt sau 256KB). Với đầu vào đối kháng (nhiều tiền tố BEGIN/rác, không có END) regex có thể mất thời gian siêu tuyến tính, và redact_secrets được gọi trên user_input/recalled_traces từ L1 staging do bên ngoài đưa vào → vector DoS trong drain_l1_staging/consolidate_batch (đang giữ write lock WAL).
**Remediation**: `Giảm trần payload (ví dụ 16–32KB) cho redaction; hoặc thay pattern private-key bằng quét dòng-theo-dòng có trạng thái (stateful tokenizer) thay vì regex có lookahead lồng nhau. Thêm test adversarial 256KB và benchmark thời gian chạy.`

### 6. [MEDIUM] VULN-006: CAS generation trong flush_outbox có thể mồ côi bản ghi InFlight
**Description**: Nếu `generation` bị tăng (re-promotion qua ON CONFLICT DO UPDATE generation+1) giữa pha claim (SELECT COALESCE(generation,1)) và pha 3 (UPDATE ... AND COALESCE(generation,1)=ob_gen), câu UPDATE CAS không khớp (rowcount=0). Hàng vẫn ở trạng thái InFlight giữ owner_token cũ cho tới khi lease 180s hết hạn; trong khoảng đó dữ liệu đã ghi ra file nhưng DB báo InFlight → lần retry sau stale-reset có thể tăng success_count trùng (nếu generation/fencing không khớp đúng) hoặc trì hoãn không cần thiết. Là race có biên nhưng có thể gây double-reinforce.
**Remediation**: `Trong pha 3, nếu UPDATE CAS trả rowcount=0, ghi nhận lease_mismatch, set status='Pending' và tăng retry_count một cách xác định (không để mồ côi). Bổ sung test mô phỏng generation bump đồng thời giữa hai pha.`

### 7. [MEDIUM] VULN-007: revert_invariant: docstring mâu thuẫn code, không đặt superseded_by=NULL
**Description**: Docstring tuyên bố khi demote V2 sẽ đặt superseded_by=NULL ('prevents 2-way cycles') nhưng code đặt `superseded_by = superseded_id` (trỏ V2→V1). Mặc dù không tạo chu trình (V1 Active, superseded_by=NULL), sự lệch đặc tả gây hiểu nhầm và làm các công cụ audit/read path dựa vào docstring đánh giá sai tính nhất quán chuỗi superseded_by.
**Remediation**: `Sửa docstring cho khớp hành vi thực (giữ back-pointer tới V1 để trace ngược) hoặc sửa code đặt NULL theo đặc tả; thêm test khẳng định bất biến chuỗi.`

## 3. Concurrency, Race Condition & Mutex Hazards (5 identified)
- **Resource**: `SQLite WAL write lock trong drain_l1_staging/consolidate_batch` | **Hazard**: Lock held during CPU-bound redaction | **Mitigation**: redact_secrets (regex) chạy trên từng dòng trong khi đang giữ BEGIN IMMEDIATE. Với payload lớn, regex có thể giữ write lock lâu, chặn writer khác. Nên redact trước khi vào transaction, hoặc giới hạn kích thước payload (đã có nhưng 256KB quá lớn).
- **Resource**: `FileLock (proven_traces.json.lock) và SQLite connection` | **Hazard**: Lock ordering / potential deadlock nếu gọi record_trace trong transaction | **Mitigation**: flush_outbox đã tách Phase 2 (file I/O) ra ngoài transaction — đúng. Tuy nhiên cần assert bất biến: không được gọi save_traces/record_trace khi conn.in_transaction=True ở bất kỳ call-site mới nào; thêm guard runtime tương tự flush_outbox trong record_trace/save_traces.
- **Resource**: `_CACHE (mtime cache) của load_traces` | **Hazard**: mtime granularity dẫn tới cache cũ (stale read) | **Mitigation**: Trên FS có granularity thô (FAT/2s), hai lần ghi trong cùng giây có thể có cùng mtime → load_traces trả cache cũ. Thêm content-hash hoặc sequence token vào cache key, hoặc buộc re-read khi vừa ghi trong cùng process.
- **Resource**: `_PROCESS_LOCKS` | **Hazard**: Tăng trưởng không giới hạn (memory leak nhẹ) | **Mitigation**: Mỗi đường dẫn lock mới tạo một RLock vĩnh viễn trong _PROCESS_LOCKS. Thêm cơ chế LRU/refcount hoặc dùng weakref để giải phóng khi không còn FileLock nào tham chiếu.
- **Resource**: `MemorySingleWriter._committed_sequence và _failed_sequences` | **Hazard**: Báo cáo trạng thái không đầy đủ | **Mitigation**: Cần cờ 'dropped failures' như VULN-002; đồng thời đảm bảo _committed_sequence không vượt qua một task còn treo do queue.Full trước đó.

## 4. Defensive Failure Scenarios & Edge Cases (6 verified)
### 1. Exception có __cause__ tự tham chiếu (raise e from e) đi qua is_transient_io_error
- **Consequence**: RecursionError, worker flush/consolidate sập, outbox kẹt InFlight.
- **Mitigation**: Visited-set theo id() + giới hạn độ sâu 16 trong is_transient_io_error; test hồi quy với cause-cycle.

### 2. Hơn 256 lần ghi thất bại trong MemorySingleWriter trước khi flush() được gọi
- **Consequence**: flush() trả về im lặng như thành công dù đã mất dữ liệu (silent write failure).
- **Mitigation**: Theo dõi dropped_failures và raise trong flush()/close(); hoặc đẩy failure vào dead-letter bền vững.

### 3. Nâng cấp in-place: workspace_episodic_memory đã có hash cũ (normpath), engine mới tính hash realpath+NFC
- **Consequence**: Bản ghi không khớp hash mới → vô hình, kiểm tra authorized_hashes sai, hành vi isolation không xác định.
- **Mitigation**: Migration re-key + dual-read 64-hex/hỗ trợ alias hash cũ trong giai đoạn chuyển tiếp; test với symlink và NFC/NFD.

### 4. Input 256KB chứa nhiều '-----BEGIN ... PRIVATE KEY-----' nhưng không có '-----END' (đối kháng)
- **Consequence**: Regex private-key tốn thời gian siêu tuyến tính, giữ write lock WAL, DoS consolidation.
- **Mitigation**: Giảm trần payload redaction; thay bằng stateful line scanner; benchmark adversarial.

### 5. Generation bị tăng đồng thời (re-promotion) giữa claim và commit trong flush_outbox
- **Consequence**: CAS không khớp, bản ghi mồ côi InFlight; retry sau 180s có thể reinforce trùng.
- **Mitigation**: Xử lý rowcount=0 thành lease_mismatch có xác định; fencing theo generation ở cả file (last_outbox_generation) và DB.

### 6. revert_invariant được gọi với memory_id tồn tại ở nhiều workspace_hash và không truyền workspace_hash
- **Consequence**: Code xử lý: trả False + log (không mơ hồ hóa) — đúng. Nhưng nếu caller nuốt False sẽ bỏ qua lỗi.
- **Mitigation**: Giữ hành vi fail-closed; caller phải phân biệt False (không tìm thấy) với raise; thêm test đa tenant.

## 5. Prescriptive Remediation Directives (9 items)
- Thêm visited-set + giới hạn độ sâu cho is_transient_io_error trước khi merge (VULN-001).
- Loại bỏ mọi `except Exception: pass` mang tính logic; chuyển thành log có persist_diag + cờ degraded, đặc biệt ở ConsolidatorEngine.__init__ registry sync (VULN-004).
- Không evict failure chưa báo cáo trong MemorySingleWriter; flush()/close() phải surface lỗi (VULN-002).
- Viết migration re-key cho canonical_workspace_hash thay đổi (realpath+NFC) + dual-read hash cũ (VULN-003).
- Giảm trần payload redaction hoặc thay regex private-key bằng stateful scanner; thêm test ReDoS adversarial (VULN-005).
- Xử lý rowcount=0 trong flush_outbox pha 3 như lease_mismatch có xác định, không để mồ côi InFlight (VULN-006).
- Đồng bộ docstring/code của revert_invariant và thêm test bất biến chuỗi superseded_by (VULN-007).
- Giữ nguyên kết luận tích cực: toàn bộ truy vấn SQL đã dùng tham số `?`/named param, kể cả _chunked_execute và search_fts5 MATCH (không có SQL injection).
- Thêm guard runtime trong record_trace/save_traces: cấm gọi khi conn.in_transaction=True để bảo toàn thứ tự lock (FileLock phải đứng ngoài transaction SQLite).

## 6. Council Gate Final Verdict: `CONDITIONAL_PASS`
