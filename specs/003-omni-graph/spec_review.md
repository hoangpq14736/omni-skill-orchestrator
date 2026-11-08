<!-- OMNI_AUDIT_META: {"verdict":"APPROVED","target_file":"spec.md","input_hash":"sha256:3177d0122a496f72b6ce08f5c66a00ec5bc3bba60f7f8a400c932de8d22c563e","model":"deepseek-flash","hash_domain":"raw_file_v1","hash_algo":"sha256-v2","timestamp_utc":"2026-11-07T20:13:18.629422+00:00","workspace_hash":"0f03e216b4ff8ec39315d4d9db720f619c14f85e5358e2aec11b48be314ab9eb","signature":"628af559ccf7b4bd957202b59940ee0bb9a990ea242833eedcada89b424e21f2"} -->

# 🛡️ Architectural Red-Teaming Audit: spec.md
**Audit Status**: `APPROVED` | **Model**: `deepseek-flash` | **Confidence**: `0.85` | **Timestamp**: `2026-11-07T20:13:18.629422+00:00`

## Executive Summary
Spec Omni-Graph là một thiết kế thực dụng, nhất quán và đúng tinh thần 'dùng tốt không lỗi' cho dự án cá nhân: 100% stdlib (ast + sqlite3 WAL), DB tách vật lý khỏi omni_memory.db, ba guard (signature/lifecycle/blast-radius) bám sát đúng 3 root cause của sự cố SVBot. DDL, index covering và Recursive CTE đều hợp lý, có cơ chế chống cycle bằng delimiter token và fail-soft khi DB thiếu/lock. Các vấn đề còn lại là thiếu sót vận hành và tinh chỉnh ngưỡng (resolution cho call qua attribute chain, ồn ào của FAIL-08, xung đột SLA <25ms với busy_timeout 100ms, ProcessPoolExecutor trên Windows vs cold-start <100ms, edge mồ côi sau khi xoá file) — không phá vỡ luồng sử dụng thường ngày, chỉ cần siết lại bằng các directive bên dưới.

## 1. Constitutional & Ring 0 Invariants Verification
- ✅ Ring 0 Security (Zero-Trust SQL & Credential Redaction): PASS
- ✅ Principle I Reflex Latency Boundary: PASS
- ✅ Concurrency & Physical Resource Bounds: PASS

## 2. Top Critical Architectural Vulnerabilities (0 identified)
_No critical vulnerabilities identified. (Zero-defect floor verified)_

## 3. Concurrency, Race Condition & Mutex Hazards (4 identified)
- **Resource**: `codebase_graph.db (ghi đồng thời bởi micro-index hook sau edit + cold sweep + pre-flight delta)` | **Hazard**: SQLITE_BUSY / write-write contention khi nhiều writer trong cùng một workspace, đặc biệt nếu hook chạy trong process con | **Mitigation**: Luôn BEGIN IMMEDIATE cho transaction ghi, busy_timeout=5000 cho writer, và gom toàn bộ re-index của một file vào một transaction duy nhất (delete nodes/edges + insert + update file_hashes). Với hook PreInvocation, dùng kết nối read-only riêng và bỏ qua write path.
- **Resource**: `file_hashes ↔ nodes (FK ON DELETE CASCADE) và bảng edges (không có FK)` | **Hazard**: Index không nhất quán khi hai process cùng re-index một file: một bên xoá nodes rồi bên kia chèn lại, sinh cặp node/edge trùng hoặc mồ côi tạm thời | **Mitigation**: Khoá theo file bằng một dòng trong file_hashes với UPDATE ... WHERE file_path=? làm 'lock marker', hoặc đơn giản là single-writer: chỉ process chính của Omni-Kernel được ghi, worker chỉ đọc. Chấp nhận được ở quy mô cá nhân.
- **Resource**: `ProcessPoolExecutor khi cold scan (NFR-001)` | **Hazard**: Nhiều worker process cùng mở SQLite và ghi schema/khởi tạo bảng lần đầu → race trên CREATE TABLE/schema init | **Mitigation**: Process cha tạo thư mục + chạy toàn bộ DDL/PRAGMA trước, đóng kết nối, rồi mới fan-out parse. Worker chỉ trả về kết quả parse (pure data) cho cha ghi tuần tự vào DB.
- **Resource**: `Hook PreInvocation SLA <25ms và busy_timeout=100ms` | **Hazard**: Tranh chấp đọc/ghi khiến hook block tới 100ms, vượt SLA và làm chậm phản hồi turn | **Mitigation**: Đặt busy_timeout rất nhỏ (0–5ms) cho kết nối của hook; nếu bận thì fail-soft và bỏ advisory (đã có FR-014). Chỉ resolver/background mới dùng timeout dài.

## 4. Defensive Failure Scenarios & Edge Cases (9 verified)
### 1. Call qua attribute chain hoặc dependency inject: `self.docker_manager.start_server(...)`, `mgr.start_server(...)` với `mgr` là tham số được inject (không phải `mgr = DockerManager()` như FR-006 Tier 4 giả định)
- **Consequence**: resolved_target_id = NULL → guard im lặng bỏ qua, tức là chính lỗi `allocated_ram` của SVBot có thể KHÔNG bị bắt; người dùng tưởng graph đã cover nhưng thực tế không
- **Mitigation**: Bổ sung tầng resolution thứ 5: (a) suy luận từ type annotation của tham số (`docker_manager: DockerManager`), (b) tra `self.<attr>` theo assignment trong `__init__`, (c) fallback theo tên method nếu tên đó là duy nhất trong workspace. Mọi kết quả fallback gắn confidence=LOW và chỉ phát advisory, không FAIL cứng. Ghi log số call UNRESOLVED để biết độ phủ thực tế.

### 2. Coroutine được tiêu thụ gián tiếp hợp lệ: `asyncio.gather(fetch_token(), other())`, `create_task(fetch_token())`, `return fetch_token()`, hoặc gán `t = fetch_token()` rồi `await t` ở dòng sau
- **Consequence**: FAIL-08 bắn false positive hàng loạt, làm nhiễu báo cáo và khiến agent bỏ qua guard
- **Mitigation**: Chỉ báo FAIL-08 khi call là biểu thức độc lập (ast.Expr) hoặc kết quả bị vứt bỏ; whitelist gather/create_task/ensure_future/run_coroutine_threadsafe/wait_for; nếu kết quả được gán biến hoặc return thì hạ xuống advisory.

### 3. Cold-start theo FR-019 (<100ms cho ≤50 files) dùng ProcessPoolExecutor như NFR-001
- **Consequence**: Trên Windows, spawn process + import interpreter đã tốn 100–300ms → mâu thuẫn SLA, lần turn đầu tiên bị chậm đúng lúc cần nhanh nhất
- **Mitigation**: Ngưỡng thích ứng: parse tuần tự trong-process khi ≤200 files (ast thuần rất nhanh, thường <50ms), chỉ bật ProcessPoolExecutor khi vượt ngưỡng. Ghi rõ trong spec rằng NFR-001 áp dụng cho repo lớn, FR-019 cho repo nhỏ.

### 4. Xoá/đổi tên file: FR/EC-014 chỉ dựa vào cascade của nodes
- **Consequence**: edges không có FK tới nodes nên các edge có file_path của file đã xoá (và các edge trỏ tới node đã biến mất) tồn tại vĩnh viễn, làm sai blast radius và phình DB theo thời gian
- **Mitigation**: Trong cùng transaction xoá file, chạy tường minh: DELETE FROM edges WHERE file_path = ?; và DELETE FROM edges WHERE target_id IN (SELECT id FROM nodes WHERE file_path = ?) trước khi xoá file_hashes; định kỳ chạy lệnh dọn edge có target_id không còn tồn tại (trừ DYNAMIC_CALL/EXTERNAL).

### 5. Hai lời gọi cùng một hàm trên cùng một dòng: `foo(foo(1))`
- **Consequence**: PRIMARY KEY (source_id, target_id, relation_type, line_number) gộp mất một call site, blast radius và kiểm tra kwargs có thể thiếu một vế
- **Mitigation**: Thêm cột `col_offset` (và/hoặc `end_col_offset`) vào edges và vào PRIMARY KEY — rẻ, không ảnh hưởng index hiện có, loại bỏ hoàn toàn va chạm.

### 6. File đang trong trạng thái SYNTAX_ERROR (agent vừa sửa dở), EC-009 giữ lại nodes cũ
- **Consequence**: Guard kiểm tra call site mới dựa trên signature cũ (phantom), có thể báo sai hoặc bỏ sót đúng lúc agent đang sửa — thời điểm quan trọng nhất
- **Mitigation**: Đánh dấu nodes thuộc file SYNTAX_ERROR bằng cờ `stale` (hoặc lọc theo parse_status), và với các call trỏ vào node stale chỉ phát advisory 'signature chưa xác thực được', tuyệt đối không FAIL cứng.

### 7. Đặt tên tier mâu thuẫn: Scenario 3.3 dùng 'Tier 1 = Direct Impact' theo hop, FR-013 dùng 'Tier 1 = Low <25' theo score; Scenario 3.5 gọi 38 callers là 'Tier-1 Blast Radius'
- **Consequence**: Cùng một nhãn mang hai nghĩa; với công thức FR-013, 38 direct callers cho score ≥95 (Tier 4 Critical) — mọi hàm tiện ích đều 'Critical', tiering mất tác dụng phân loại
- **Mitigation**: Tách hai khái niệm: `hop_class` (DIRECT/NEAR/FAR theo số hop) và `risk_score` (0–100). Đặt lại hệ số (ví dụ 1.0*direct + 0.3*transitive + 2.0*files) để tier phân bố thực tế trên repo cá nhân, hoặc đơn giản hoá còn 3 mức LOW/MEDIUM/HIGH theo ngưỡng direct+transitive.

### 8. Recursive CTE dùng UNION (dedup) cùng path_tokens/display_chain khác nhau trên đồ thị dày
- **Consequence**: Chi phí sort/dedup gần như vô ích vì path_tokens luôn khác nhau, đe doạ SLA <0.30ms khi số đường đi bùng nổ ở 4 hop
- **Mitigation**: Dùng UNION ALL kèm depth bound và cycle guard (đã có), dedup ở tầng cuối bằng GROUP BY như hiện tại; giữ covering index idx_edges_tgt_rel.

### 9. FAIL-07 (renamed parameter drift) tham chiếu `renamed_params` nhưng không có bảng/entity/nguồn dữ liệu nào trong DDL hay Domain Model
- **Consequence**: Không rõ nạp mapping từ đâu → FAIL-07 sẽ không bao giờ bắn, hoặc bị implement tuỳ hứng, gây lệch giữa spec và code
- **Mitigation**: Chốt nguồn: file cấu hình `specs/003-omni-graph/renamed_params.json` (key = 'file.py:Class.method', value = {old: new}) nạp lúc khởi tạo và cache trong bộ nhớ; nếu file không tồn tại thì FAIL-07 tắt êm, mọi unknown keyword rơi về FAIL-03.

## 5. Prescriptive Remediation Directives (9 items)
- Ưu tiên tuyệt đối false-positive thấp hơn false-negative trong giai đoạn đầu: mọi kết quả resolution có confidence thấp (fallback theo tên, đa hình, wildcard import) chỉ được phát advisory, không FAIL cứng — nếu không agent sẽ học cách bỏ qua guard.
- Bổ sung tầng resolution theo type annotation và theo assignment `self.x = X()` trong `__init__` trước khi hạ cấp sang fallback theo tên duy nhất; đây là điều kiện để kịch bản SVBot thực sự được bắt.
- Chốt single-writer: chỉ tiến trình chính của Omni-Kernel ghi vào codebase_graph.db; hook và worker chỉ đọc hoặc trả dữ liệu thô. Điều này xoá luôn phần lớn hazard về lock mà không cần cơ chế phức tạp.
- Đặt busy_timeout = 2ms cho kết nối trong hook_runner.py, giữ 5000ms cho writer/resolver; fail-soft im lặng khi bận để bảo toàn SLA <25ms.
- Tách rõ `hop_class` và `risk_score` trong BlastRadiusReport, đổi tên tier để không trùng nhãn giữa Scenario 3.3, 3.5 và FR-013; hiệu chỉnh hệ số trên chính repo này trước khi ratify.
- Thêm `col_offset` vào PRIMARY KEY của edges; thêm bước xoá edge tường minh khi file bị xoá/đổi tên; thêm script dọn edge mồ côi chạy thủ công (không cần daemon).
- Thêm bảng/cột lưu `parse_status` + cờ stale trên nodes và dùng nó để suppress FAIL cứng với file đang SYNTAX_ERROR.
- Chốt ngưỡng chuyển serial → ProcessPoolExecutor (đề xuất 200 files) và ghi rõ trong NFR-001 để hai yêu cầu FR-019/NFR-001 không mâu thuẫn trên Windows.
- Giữ nguyên các ràng buộc đã ratify: 100% stdlib, parameterized SQL, tách vật lý hai DB, auto-append .gitignore — không thêm dependency nào ngoài stdlib.

## 6. Council Gate Final Verdict: `APPROVED`
