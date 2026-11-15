<!-- OMNI_AUDIT_META: {"verdict":"APPROVED","target_file":"OMNI_KERNEL_V4.3_UPGRADE_PROPOSAL.md","input_hash":"sha256:87b280dd49431b76fcf70ac938d9a2c84c187ed7221f7fe926696f3027d465ad","model":"deepseek-flash","hash_domain":"raw_file_v1","hash_algo":"sha256-v2","timestamp_utc":"2026-11-15T14:05:42.899069+00:00","workspace_hash":"bdc5f8de8375a5285f35af3ff09dd598a712a1d773ec36e26c730617f6eebb3b","signature":"b0e9321c2523b2bb7dfe6cc3fc6667d8ef46658555fbd7d6e0a5c9363119a6e4"} -->

# 🛡️ Architectural Red-Teaming Audit: OMNI_KERNEL_V4.3_UPGRADE_PROPOSAL.md
**Audit Status**: `APPROVED` | **Model**: `deepseek-flash` | **Confidence**: `0.94` | **Timestamp**: `2026-11-15T14:05:42.899069+00:00`

## Executive Summary
Đề xuất Omni-Kernel v4.3 có phạm vi rõ ràng, ưu tiên đúng các lỗi vận hành thực tế trên Windows, và phù hợp với dự án cá nhân: sửa fallback FTS5, giảm latency hook, debounce consolidator, mở rộng retry worker, và đồng bộ Plan Gate. Có vài điểm cần guard khi triển khai, đặc biệt là phụ thuộc NumPy trong Spec 3/4 và giả định schema partition_id, nhưng không có lỗi kiến trúc nghiêm trọng nào chặn sử dụng cá nhân.

## 1. Constitutional & Ring 0 Invariants Verification
- ✅ Ring 0 Security (Zero-Trust SQL & Credential Redaction): PASS
- ✅ Principle I Reflex Latency Boundary: PASS
- ✅ Concurrency & Physical Resource Bounds: PASS

## 2. Top Critical Architectural Vulnerabilities (0 identified)
_No critical vulnerabilities identified. (Zero-defect floor verified)_

## 3. Concurrency, Race Condition & Mutex Hazards (4 identified)
- **Resource**: `.omni/last_consolidator_spawn.timestamp.lock` | **Hazard**: stale-lock takeover race | **Mitigation**: Ghi PID/thời điểm tạo lock; chỉ xóa lock khi owner đã chết hoặc TTL >120s; tránh unlink mù quáng có thể xóa lock của process mới.
- **Resource**: `SQLite omni_memory.db` | **Hazard**: multi-writer contention | **Mitigation**: Giữ MemorySingleWriter, dùng BEGIN IMMEDIATE và busy_timeout 5000ms; không ghi DB từ reader thread hoặc worker thread.
- **Resource**: `MCP stdout stream` | **Hazard**: interleaved JSON-RPC responses | **Mitigation**: Dùng stdout_lock cho mọi write; xử lý initialize/ping/tools-list đồng bộ trên main thread; chỉ đẩy tools/call vào ThreadPoolExecutor.
- **Resource**: `<target_file>.lock` | **Hazard**: worker thread lock contention | **Mitigation**: Spin-wait với exponential backoff + jitter; timeout rõ ràng; ghi thread id; thu hồi lock stale sau TTL thay vì crash ngay.

## 4. Defensive Failure Scenarios & Edge Cases (6 verified)
### 1. NumPy không có trong môi trường dù ONNX runtime có
- **Consequence**: Spec 3/4 vectorized scan và batch embedding crash, làm mất dense recall hoặc backfill.
- **Mitigation**: Guard import numpy; nếu thiếu thì fallback pure-Python/Fts5 hoặc tắt dense scan; coi NumPy là optional cùng ONNX Runtime.

### 2. Database mới có 0 dense embeddings
- **Consequence**: Trước Spec 2, recall_episodic_memory trả [] dù FTS5 có dữ liệu.
- **Mitigation**: Spec 2 đã sửa bằng query_vector=None và để hybrid_search fallback BM25; thêm test clean DB.

### 3. Workspace >20k vectors nhưng schema chưa có partition_id/workspace_metadata
- **Consequence**: Spec 3 query partition lỗi no such column hoặc trả rỗng.
- **Mitigation**: Chỉ partition khi cột tồn tại; nếu không, dùng unpartitioned vectorized scan hoặc giới hạn theo workspace_hash.

### 4. vector_blob bị corrupt hoặc không đúng 256 float32
- **Consequence**: np.frombuffer/reshape lỗi, dense search chết toàn bộ.
- **Mitigation**: Validate len(blob) % 4 == 0 và shape cố định; bỏ qua row lỗi, log warning, rồi backfill lại.

### 5. Verification pipeline có upstream thoát sớm hoặc xuất >64KB stderr
- **Consequence**: Deadlock hoặc wait timeout nếu không drain đúng cách.
- **Mitigation**: Drain stderr đồng thời từng stage; đóng stdout pipe upstream; dùng timeout và kill process tree; giữ pipefail semantics.

### 6. Hook chạy python -S thiếu sys.path local
- **Consequence**: Import module local thất bại, pre-flight hỏng trên một số cài đặt Windows.
- **Mitigation**: Giữ bootstrap sys.path trong hook_runner.py; chỉ dùng stdlib trong hook; test với plugin path thực tế.

## 5. Prescriptive Remediation Directives (6 items)
- Ưu tiên Spec 1 và Spec 2 trước vì là hotfix nhỏ, rủi ro thấp, sửa lỗi thực tế ngay.
- Biến NumPy thành optional dependency có guard import; nếu thiếu thì fallback FTS5/pure-Python thay vì crash.
- Spec 3 phải kiểm tra partition_id/workspace_metadata tồn tại trước khi query partition; nếu không có thì dùng scan không partition.
- Giữ MemorySingleWriter và busy_timeout; không mở writer song song từ worker threads.
- Thêm test Windows cho shutil.which, taskkill /T, CRLF stdio, và pipeline >64KB.
- Đảm bảo MCP ThreadPoolExecutor shutdown sạch khi stdin EOF để tránh treo process.

## 6. Council Gate Final Verdict: `APPROVED`
