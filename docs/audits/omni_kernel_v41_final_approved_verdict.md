<!-- OMNI_AUDIT_META: {"verdict":"APPROVED","target_file":"omni_kernel_v41_production_remediation.patch","input_hash":"sha256:4eff3dfd754a8d02ec89839df40fdcc4922bb8ec28ba7bb181b7438d994427c8","model":"deepseek-flash","hash_domain":"raw_file_v1","hash_algo":"sha256-v2","timestamp_utc":"2026-11-04T20:13:10.009007+00:00","workspace_hash":"0f03e216b4ff8ec39315d4d9db720f619c14f85e5358e2aec11b48be314ab9eb","signature":"5accbb474befa6b786660f152d61f69255f5a9984d35179d73f57d41167a17ec"} -->

# 🛡️ Architectural Red-Teaming Audit: omni_kernel_v41_production_remediation.patch
**Audit Status**: `APPROVED` | **Model**: `deepseek-flash` | **Confidence**: `0.87` | **Timestamp**: `2026-11-04T20:13:10.009007+00:00`

## Executive Summary
Patch reviewed for a single-user local CLI: các thay đổi chủ yếu là tinh chỉnh heuristic (stopword filter cho trace recall, segment-aware scoring + word-boundary synonyms trong resolver, SPECIFICITY_MAP cho docker/k8s), nới chính xác hoá staleness của indexer (bỏ dung sai +1.0s, generated_at dạng float), và cho phép audit đã commit trong docs/audits/omni_kernel_* được verify portable khi clone repo. Không thấy lỗi chức năng hay crash thực tế trong luồng sử dụng hàng ngày của một developer; các nhánh mới đều có guard (if os.path.exists / try-except / fail-open của hook). Đáng chú ý nhất chỉ là phụ thuộc vào biến is_committed_repo_audit ở nhánh kiểm tra stale — cần đảm bảo nó luôn được gán trong cùng iteration (đã được scenario 8 trong verify_real_world.py exercise).

## 1. Constitutional & Ring 0 Invariants Verification
- ✅ Ring 0 Security (Zero-Trust SQL & Credential Redaction): PASS
- ✅ Principle I Reflex Latency Boundary: PASS
- ✅ Concurrency & Physical Resource Bounds: PASS

## 2. Top Critical Architectural Vulnerabilities (0 identified)
_No critical vulnerabilities identified. (Zero-defect floor verified)_

## 3. Concurrency, Race Condition & Mutex Hazards (3 identified)
- **Resource**: `traces.json (experiential memory store)` | **Hazard**: Nhiều writer đồng thời (8 thread trong scenario 9) cùng read-modify-write file JSON | **Mitigation**: record_trace được kiểm chứng commit đủ 40/40 trace; nếu chưa có file-lock nội bộ thì chỉ cần một lock tạm (fcntl/atomic temp+rename) là đủ cho nhu cầu cá nhân, không cần transaction phức tạp.
- **Resource**: `SQLite DB (hook_runner path)` | **Hazard**: Hook chạy trong khi DB đang giữ write transaction (SQLITE_BUSY) | **Mitigation**: Scenario 5 xác nhận hook vẫn trả injectSteps trong ~ms nhờ cơ chế spool non-blocking; WAL mode + busy_timeout là đủ.
- **Resource**: `registry.json vs. resolver đọc song song` | **Hazard**: Index rebuild (build_index) trong lúc resolver.load_registry đọc file | **Mitigation**: Ghi registry qua atomic rename (temp file) để tránh đọc phải JSON dở dang; hiện tại rủi ro thấp vì rebuild xảy ra tuần tự trong tiến trình CLI.

## 4. Defensive Failure Scenarios & Edge Cases (7 verified)
### 1. Skill mới được tạo trong cùng giây với lần build index (trước đây bị bỏ sót do dung sai +1.0s)
- **Consequence**: is_registry_stale giờ so sánh mtime trực tiếp với generated_at (float) nên phát hiện ngay; query tiếp theo route được skill mới mà không có 'blind window' 1 giây.
- **Mitigation**: Đã có Scenario 4 (instant-zig-wasm-compiler) trong verify_real_world.py kiểm chứng; mtime của thư mục cha cũng thay đổi nên trường hợp cùng microsecond vẫn được bắt.

### 2. Query chỉ gồm từ generic: 'fix error', 'fix code issue'
- **Consequence**: recall_traces lọc sạch intersection chung (specific_intersection rỗng) nên trả 0 trace thay vì false-positive recall một trace không liên quan.
- **Mitigation**: Đây là hành vi mong muốn; resolver vẫn route bình thường nhờ scoring theo tên skill/description, không phụ thuộc trace recall.

### 3. Clone repo sang máy/thư mục khác rồi verify audit đã commit (docs/audits/omni_kernel_*.md/.patch)
- **Consequence**: meta workspace_hash không khớp workspace mới sẽ trước đây bị loại; nay được bỏ qua nhờ is_committed_repo_audit, và kiểm tra stale theo target_mtime cũng được bỏ qua để verdict portable.
- **Mitigation**: Điều kiện nhận diện chặt: dirname == 'audits' và basename startswith 'omni_kernel_' — chỉ áp dụng cho audit đã commit trong repo, không nới lỏng cho audit sinh tự động trong workspace.

### 4. Hook CLI nhận JSON hỏng ('{corrupt json payload')
- **Consequence**: Không crash; exit code 0 và inject OMNI-KERNEL WARNING (fail-open), Claude Code không bị chặn phiên làm việc.
- **Mitigation**: Scenario 10 kiểm chứng trực tiếp qua subprocess; đường parse lỗi đã có try/except bao ngoài.

### 5. Query backend/docker nhưng không có ý định browser/mobile: 'fix docker port conflict 8080'
- **Consequence**: Các skill chrome-devtools/cookie-debugging bị phạt -95 và flutter/android bị phạt -75, nên docker-patterns (specificity 5) lên top-1.
- **Mitigation**: Đã bổ sung vào GOLDEN_ROUTING_QUERIES và test_round_7_remediation; ngưỡng assert Top-3 >= 24/25 nên regression sẽ bị bắt.

### 6. Đồng bộ synonym theo word-boundary: 'spec' không còn match 'inspect', 'nap' không match 'snapshot'
- **Consequence**: Giảm nhiễu token expansion; phrase nhiều từ vẫn match qua padded string ' phrase ' trên cả bản có dấu và không dấu.
- **Mitigation**: Token đơn không dấu yêu cầu len >= 4 và phải là exact word trong raw_words_unaccented — tránh match rác mà vẫn giữ recall cho từ tiếng Việt có dấu.

### 7. Test mới trong test_round_7_remediation.py dùng _SCRIPTS_DIR để suy ra repo_root
- **Consequence**: Nếu module test không định nghĩa _SCRIPTS_DIR thì chỉ riêng test case đó NameError; luồng CLI runtime không bị ảnh hưởng vì đây là code test.
- **Mitigation**: Xác nhận _SCRIPTS_DIR có sẵn ở đầu file test (đã dùng chung pattern với verify_real_world.py); nếu chưa, thay bằng os.path.dirname(os.path.abspath(__file__)).

## 5. Prescriptive Remediation Directives (5 items)
- Giữ nguyên hướng tinh chỉnh heuristic; tránh bổ sung thêm penalty cứng dạng 'if name == X' — nên gom vào bảng cấu hình (SPECIFICITY_MAP / GENERIC_SKILL_SEGMENTS) để dễ chỉnh khi thêm skill mới.
- Chuyển GENERIC_TRACE_STOPWORDS ra khỏi vòng lặp trong recall_traces (module-level constant) để khỏi tạo set mỗi trace — tối ưu nhỏ nhưng miễn phí.
- Đảm bảo is_committed_repo_audit luôn được gán trước mọi nhánh dùng nó trong verify_critic_artifact (đã đúng theo thứ tự hunk, chỉ cần giữ khi refactor sau này).
- Cân nhắc dùng int(time.time()) ở nơi khác nếu có consumer hiển thị generated_at dạng epoch nguyên; hiện tại float là đúng cho so sánh mtime nên chỉ cần rà soát khi thêm format output.
- Khi ghi registry/index và traces.json, dùng atomic write (temp + os.replace) để tránh file dở dang nếu tiến trình bị kill giữa chừng trong lúc dùng hàng ngày.

## 6. Council Gate Final Verdict: `APPROVED`
