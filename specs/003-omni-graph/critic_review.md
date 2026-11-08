<!-- OMNI_AUDIT_META: {"verdict":"APPROVED","target_file":"plan.md","input_hash":"sha256:2fd83133ee000c802fac4b6367e8f8d3c26f7ec5cab1b40df705c469cf8410ac","model":"deepseek-flash","hash_domain":"raw_file_v1","hash_algo":"sha256-v2","timestamp_utc":"2026-11-07T19:20:20.908508+00:00","workspace_hash":"0f03e216b4ff8ec39315d4d9db720f619c14f85e5358e2aec11b48be314ab9eb","signature":"53bed1a483d403fe59ba6721073596b083ef22f1cc8e81aea90a18c78ad7b189"} -->

# 🛡️ Architectural Red-Teaming Audit: plan.md
**Audit Status**: `APPROVED` | **Model**: `deepseek-flash` | **Confidence**: `0.84` | **Timestamp**: `2026-11-07T19:20:20.908508+00:00`

## Executive Summary
Kế hoạch Omni-Graph rất mạch lạc và phù hợp với bối cảnh dự án cá nhân: 100% Python stdlib, SQLite cục bộ trong <workspace>/.omni/, tách biệt vật lý với Omni-Memory, không phụ thuộc mạng/CDN, chạy trên CPU và giữ nguyên headroom VRAM của MI50. Các thành phần cốt lõi (two-tier dirty check, recursive CTE blast radius có chặn chu trình, static signature binding, lifecycle drift detection, fail-soft hook advisory) đều khả thi và không có mâu thuẫn chức năng nào khiến người dùng đơn lẻ không thể vận hành. Một số điểm cần lưu ý khi triển khai (strip self/cls, xóa edge theo file_path thay vì dựa vào FK cascade, cycle-check bằng delimiter, và thứ tự MVP) đã được ghi nhận trong edge_cases/prescriptive_directives nhưng không phải là lỗi chặn. Khuyến nghị triển khai theo pha: blast radius + signature + advisory hook trước, visualizer/report/lifecycle sau (YAGNI).

## 1. Constitutional & Ring 0 Invariants Verification
- ✅ Ring 0 Security (Zero-Trust SQL & Credential Redaction): PASS
- ✅ Principle I Reflex Latency Boundary: PASS
- ✅ Concurrency & Physical Resource Bounds: PASS

## 2. Top Critical Architectural Vulnerabilities (0 identified)
_No critical vulnerabilities identified. (Zero-defect floor verified)_

## 3. Concurrency, Race Condition & Mutex Hazards (3 identified)
- **Resource**: `codebase_graph.db (reindex writer vs hook/resolver readers)` | **Hazard**: SQLITE_BUSY / read blocked during BEGIN IMMEDIATE reindex | **Mitigation**: WAL đã bật; reader mở mode=ro với busy_timeout=100ms trong hook; mọi thao tác advisory bọc try/except fail-soft; reindex per-file ngắn (<8.5ms) nên cửa sổ khóa rất nhỏ.
- **Resource**: `omni_memory.db và codebase_graph.db` | **Hazard**: Khóa chéo giữa hai database nếu dùng ATTACH hoặc transaction chung | **Mitigation**: Giữ nguyên tách biệt file vật lý, không dùng ATTACH DATABASE; mọi tổng hợp chéo thực hiện trong bộ nhớ Python như thiết kế.
- **Resource**: `Nhiều agent/tool cùng sửa file và kích hoạt micro-index` | **Hazard**: Race condition giữa hai lần reindex cùng file (lost update / node trùng) | **Mitigation**: Mỗi file dùng một transaction nguyên tử DELETE+INSERT theo canonical file_path; chấp nhận last-writer-wins (đơn người dùng); thêm khóa tiến trình nhẹ (ProcessMutex) nếu cần.

## 4. Defensive Failure Scenarios & Edge Cases (7 verified)
### 1. Kiểm tra signature cho lời gọi phương thức obj.method(...) khi signature lưu trong DB có tham số self/cls.
- **Consequence**: Validator có thể báo FAIL-02 MISSING_REQUIRED_POSITIONAL_ARG cho mọi lời gọi phương thức, tạo false positive hàng loạt và làm nhiễu tính năng signature guard.
- **Mitigation**: Khi node_type là method/async_method, loại bỏ tham số đầu (self/cls) khỏi required_pos/posonly trước khi binding; thêm unit test hồi quy cho obj.method() và @classmethod/@staticmethod.

### 2. Xóa hoặc đổi tên file nguồn; transaction ở §8.6 dựa vào 'cascading foreign keys tự động xóa edges'.
- **Consequence**: Bảng edges không có FK tới nodes/codebase_files_meta (chỉ có file_path và index), nên CASCADE không xóa edge; edge cũ tồn tại dai dẳng, làm sai blast radius và báo caller ma.
- **Mitigation**: Trong transaction nguyên tử, thêm tường minh DELETE FROM edges WHERE file_path = ?; định kỳ chạy orphan sweep (edges trỏ tới node không tồn tại) và lệnh --rebuild toàn bộ.

### 3. Phát hiện chu trình bằng instr(br.path, e.source_id) = 0 khi ID nút này là tiền tố/xâu con của ID nút khác (ví dụ scripts/foo.py:foo nằm trong scripts/foo.py:foobar).
- **Consequence**: Traversal bị cắt sớm giả tạo, blast radius thiếu node (false negative) mà không báo lỗi.
- **Mitigation**: Bọc ID bằng delimiter khi lưu path, ví dụ '|' || id || '|' và kiểm tra theo token có delimiter; hoặc lưu path dạng JSON array và kiểm tra membership.

### 4. Đồ thị dày với nhiều đường đi đơn phân biệt tới cùng một nút (mutual recursion không hoàn toàn, diamond dependencies).
- **Consequence**: UNION kèm path string không khử trùng lặp giữa các path khác nhau; số dòng CTE có thể bùng nổ tổ hợp dù đã chặn depth, gây chậm/đầy temp_store.
- **Mitigation**: Giới hạn depth mặc định 3-5; với truy vấn không cần path, dùng UNION trên (node_id) hoặc bảng visited tạm; benchmark trên repo thật trước khi tăng depth.

### 5. File đang được sửa dở gây SyntaxError tạm thời.
- **Consequence**: Nếu giữ node cũ, blast radius và signature có thể phản ánh trạng thái cũ; nếu xóa, graph mất thông tin tạm thời.
- **Mitigation**: Đánh dấu parse_status='SYNTAX_ERROR', giữ node cũ nhưng gắn cờ cảnh báo trong báo cáo/advisory; re-parse ngay khi file được lưu hợp lệ; không làm hỏng vòng lặp agent.

### 6. Windows path casing/Unicode: os.path.normcase hạ chữ thường, đường dẫn hiển thị bị đổi khác bản gốc.
- **Consequence**: ID nút ổn định nhưng hiển thị trong report/visualizer có thể khác thực tế; gây khó đọc.
- **Mitigation**: Lưu canonical lowercase trong ID nhưng thêm cột display_path giữ nguyên đường dẫn gốc cho báo cáo; chuẩn hóa Unicode NFC trước khi hash/so sánh.

### 7. Hook mở DB read-only đúng lúc SQLite đang checkpoint WAL hoặc vừa rebuild.
- **Consequence**: Có thể gặp SQLITE_BUSY hoặc đọc snapshot cũ trong thời gian ngắn.
- **Mitigation**: busy_timeout=100ms, bọc try/except fail-soft, coi đây là advisory không chặn; WAL cho phép reader nhất quán theo snapshot.

## 5. Prescriptive Remediation Directives (7 items)
- Triển khai theo pha MVP trước (YAGNI): codebase_files_meta + nodes + edges + edges/signatures + recursive blast radius + fail-soft hook advisory; hoãn visualizer, markdown report và lifecycle invariants sang pha 2 sau khi graph lõi ổn định.
- Trong transaction nguyên tử reindex, xóa edge tường minh bằng DELETE FROM edges WHERE file_path = ?; không dựa vào FK cascade cho edges. Bổ sung lệnh --rebuild để phục hồi khi graph bị drift.
- Loại bỏ self/cls khỏi signature binding cho method/async_method; thêm test hồi quy cho instance/class/static method để tránh false positive FAIL-02.
- Dùng kiểm tra chu trình an toàn delimiter (ví dụ '|' || id || '|') hoặc JSON array membership thay cho instr(path, id) thô.
- Giữ signature/lifecycle guard ở chế độ advisory-only, mỗi file cô lập lỗi (try/except SyntaxError), tuyệt đối không chặn hay làm chậm quá SLA vòng lặp agent.
- Bỏ qua file >2MB, thư mục .git/node_modules/.venv/__pycache__; giữ PRAGMA cache_size và temp_store như thiết kế để tránh bộ nhớ phình to.
- Tài liệu hóa rõ heuristic resolution (scope cục bộ, import tuyệt đối/tương đối, class binding) và giới hạn của nó để người dùng hiểu false positive/negative có thể xảy ra với metaprogramming.

## 6. Council Gate Final Verdict: `APPROVED`
