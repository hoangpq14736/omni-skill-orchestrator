# 🧠 Omni-Kernel v4.1: Hệ Điều Hành Nhận Thức Tự Trị Toàn Năng

[![Agent Plugins 1.0.0](https://img.shields.io/badge/Spec-Agent%20Plugins%201.0.0-blue.svg)](https://agent-plugins.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)
[![Zero Dependency Kernel](https://img.shields.io/badge/Dependencies-0%20(Pure%20Stdlib%20Kernel)-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-277%2F277%20Passing-success.svg)]()
[![Council Gate](https://img.shields.io/badge/DeepSeek%20Council%20Gate-APPROVED-brightgreen.svg)](docs/audits/omni_kernel_v41_final_approved_verdict.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) • [Tiếng Việt](README.vi.md)

> **Hệ điều hành Nhận thức AI Tự trị Toàn năng dành cho Google Antigravity, Claude Code, Cursor và các Framework Tác tử AI.**  
> *Trang bị Kiến trúc Trí nhớ Đa tầng Tri-Tier Omni-Memory v4.1, Giám sát viên Kiến trúc Độc lập Omni-Auditor (DeepSeek-V4.1-Flash), Hạm đội Tác nhân Không đồng nhất (Groq Cloud LPU + Local MI50 GPU), Bộ quy trình Đặc tả Kỹ thuật Chuẩn GitHub Spec Kit (SDD), và Điều phối Kỹ năng JIT với 0 static token lãng phí.*

---

## ⚡ Tại sao cần Omni-Kernel?

Các hệ thống tác tử AI truyền thống thường đối mặt với vấn đề phình to ngữ cảnh (Context Bloat), luật lệ cứng nhắc, hao tổn hạn ngạch token nhanh chóng và thiếu khả năng thích ứng trước các công nghệ lạ.

| Tiêu chí | Hệ thống Kỹ năng Tĩnh Truyền thống | Omni-Kernel v4.1 |
|---|---|---|
| **Dung lượng Ngữ cảnh (Tokens)** | Nhồi 50–120 kỹ năng & quy tắc tĩnh vào System Prompt (**15.000–25.000 tokens**), gây tràn ngữ cảnh và suy giảm IQ của mô hình. | **< 300 Tokens ở trạng thái chờ!** Giữ nguyên tắc Ring 0 tinh gọn; kỹ năng, quy tắc miền và công cụ được phân giải Đúng Lúc (JIT). |
| **Trí nhớ Dài hạn (Memory)** | Dùng file JSON phẳng hoặc vector DB cồng kềnh, dễ mất dữ liệu hoặc làm chậm phiên chat (>500ms). | **Trí nhớ Đa tầng Tri-Tier Omni-Memory**: Tầng 1 Phản xạ RAM (<0.3ms); Tầng 2 SQLite WAL nhúng FTS5 BM25 + CPU ONNX Embeddings (<15ms, 0MB VRAM Tax); Tầng 3 Consolidator tự động tính độ trôi dạt Ebbinghaus. |
| **Kiểm soát Kiến trúc (Architecture)** | Subagent nội bộ tự sinh dễ rơi vào "Buồng vang tự sướng" (Echo Chamber), tự khen chính mình. | **Omni-Auditor Gatekeeper (DeepSeek-V4.1-Flash)**: Phản biện độc lập bên ngoài (Red-teaming Devil's Advocate, 1M context), cưỡng chế kiểm tra qua `hook_runner.py` mà không gây nghẽn luồng hook. |
| **Thực thi Mã nguồn (Worker Fleet)** | Mô hình chính phải tự gõ từng dòng boilerplate, tốn kém token và chậm chạp. | **Hạm đội Worker Chuyên trách**: Groq Cloud LPU (300-800+ tok/s sinh boilerplate/test) song song cùng Local AMD MI50 GPU (100% offline, local fast edit, SQLite WAL). |
| **Quy trình Phát triển (SDD)** | Bắt tay vào viết code ngay mà không có đặc tả, dễ gây lỗi phân kỳ và phá vỡ kiến trúc. | **Tích hợp Bản địa GitHub Spec Kit**: Chuẩn hóa vòng đời 10 phase (Constitution, Specify, Plan, Tasks, Implement, Converge...). |
| **Tốc độ & Phụ thuộc** | Phụ thuộc thư viện cồng kềnh ngoài luồng, dễ dính lỗi tương thích môi trường. | **Lõi Python Standard Library thuần túy (0 External Dependencies cho Kernel, Hook & FTS5)**. Quét 500+ kỹ năng trong **0.12s**, phân giải trong **~1ms** với tốc độ **1.000+ QPS**. Tùy chọn tăng tốc CPU ONNX cho Tầng 2 (với cơ chế tự động hạ cấp an toàn về SQLite FTS5 BM25 thuần stdlib nếu máy chưa cài ONNX). |

---

## 🏗️ Kiến trúc Hệ thống

Omni-Kernel v4.1 vận hành theo mô hình phân tầng chặt chẽ:

```text
                      ┌────────────────────────────────────────────────────────┐
                      │              CHỈ HUY TRƯỞNG: ANTIGRAVITY               │
                      │               (Lập kế hoạch, UI, Điều phối)            │
                      └───────────────────────────┬────────────────────────────┘
                                                  │
                                                  ▼
                      ┌────────────────────────────────────────────────────────┐
                      │       HARD GATEKEEPER HOOK (hook_runner.py, <25ms)     │
                      │  - Tầng 1: L1 Reflex RAM Cache (<0.3ms, 0 Token)       │
                      │  - Quét phát hiện RFC / SDD / Git Diff lớn (<1ms)      │
                      │  - Cưỡng chế tiêm chỉ thị cứng vào Ephemeral Context   │
                      └───────────────────────────┬────────────────────────────┘
                                                  │ (Bắt buộc Chỉ huy phải gọi Auditor)
                                                  ▼
                                  ┌────────────────────────────────┐
                                  │   DEEPSEEK-V4.1-FLASH AUDITOR  │
                                  │   (Tổng Giám sát Kiến trúc)   │
                                  │   - Cửa sổ 1M tokens           │
                                  │   - Red-Teaming Persona        │
                                  │   - Zero Echo-Chamber          │
                                  └───────────────┬────────────────┘
                                                  │
                         ┌────────────────────────┴────────────────────────┐
                         ▼ (Approved)                                      ▼ (Rejected / Critique)
            ┌───────────────────────────┐                         ┌──────────────────┐
            │   HẠM ĐỘI DUAL WORKERS    │                         │ Trả về phản biện │
            ├─────────────┬─────────────┤                         │ Yêu cầu tinh chỉnh│
            │  Local MI50 │  Groq Cloud │                         └──────────────────┘
            │  (AMD 16GB) │  (LPU 120B) │
            │ SQLite WAL  │ Sinh test & │
            │ 100% offline│ boilerplate │
            └─────────────┴─────────────┘
```

> **⚡ Làm rõ về cơ chế Phân tách Hook & SLA:** Tiến trình `hook_runner.py` cam kết hoàn tất trong `<25ms` vì nó **KHÔNG thực hiện gọi mạng đồng bộ tới DeepSeek API** trong luồng hook. Thay vào đó, hook chỉ làm nhiệm vụ xác thực tính tươi mới của artifact trên đĩa, đối chiếu mã hash SHA-256, và tiêm chỉ thị bắt buộc (`[CRITICAL ARCHITECTURE GATEKEEPER DIRECTIVE]`) để ép Agent Chỉ huy phải chủ động gọi công cụ MCP `deepseek_worker_cloud` trước khi được phép chuyển sang phase tiếp theo.

---

## 🧠 Kiến trúc Trí nhớ Đa tầng Tri-Tier Omni-Memory v4.1

Toàn bộ tri thức, giải pháp khắc phục lỗi đã được chứng thực, và dấu vết thực thi được quản trị qua 3 tầng:

1. **Tier 1 (L1 Ephemeral Reflex - <0.3ms reflex, <25ms hook turnaround)**:
   - Hook tiền khởi chạy viết bằng 100% Python Standard Library trong `scripts/hook_runner.py`.
   - Đọc bộ đệm RAM nhanh từ `scripts/proven_traces.json` trong <0.02ms.
   - Ghi nhật ký bất đồng bộ vào bộ đệm `l1_staging_log` trong cơ sở dữ liệu SQLite mà không làm chậm phiên tương tác.

2. **Tier 2 (L2 Hybrid Episodic Memory - <15ms retrieval, 0MB VRAM Tax)**:
   - Cơ sở dữ liệu SQLite nhúng tại `omni_memory.db` kích hoạt chế độ **WAL mode** (`PRAGMA synchronous = NORMAL;`, `busy_timeout = 5000;`).
   - Tìm kiếm hỗn hợp kết hợp **Dual-Column FTS5 BM25** (`content_exact` trọng số 10.0 vs `content_folded` trọng số 1.0) song song với **CPU ONNX Embeddings** (`paraphrase-multilingual-MiniLM-L12-v2`, INT8 quantization, 0MB VRAM, ~7ms) qua thuật toán Reciprocal Rank Fusion ($k=20$).
   - *Cơ chế Hạ cấp An toàn (Graceful Degradation):* Nếu môi trường chưa cài đặt `onnxruntime`, hệ thống tự động fallback về chế độ 100% thuần stdlib SQLite FTS5 BM25 mà không gây ra bất kỳ lỗi gián đoạn nào.

3. **Tier 3 (L3 Background Consolidator Daemon)**:
   - Tiến trình chạy ngầm `scripts/consolidator.py` tiêu thụ các bản ghi từ `l1_staging_log`.
   - Tự động thăng hạng vết tri thức đa kích hoạt ($\ge 2$ lần thành công) kèm gán nhãn song ngữ tự động.
   - Áp dụng công thức suy giảm ổn định Ebbinghaus và sử dụng `PRAGMA wal_checkpoint(PASSIVE);` để chống hoàn toàn xung đột khóa file trên Windows NTFS.

---

## 🛠️ Danh mục Module Cốt lõi

| Thành phần | Đường dẫn | Mô tả chức năng |
|---|---|---|
| **Omni-Auditor Gatekeeper** | `scripts/consult_critic.py` | Client REST 100% stdlib kết nối DeepSeek-V4.1-Flash API phản biện kiến trúc độc lập (1M context, 30s timeout, jittered backoff). |
| **Auditor MCP Server** | `mcp/deepseek_worker_mcp.py` | Máy chủ JSON-RPC 2.0 xuất xưởng 2 công cụ `deepseek_audit_spec` và `deepseek_audit_diff`. |
| **Tri-Tier Memory Engine** | `scripts/memory_engine.py` | Lõi tìm kiếm bộ nhớ hỗn hợp FTS5 BM25 + ONNX Dense Vector Embeddings với RRF ranking. |
| **Memory Consolidator** | `scripts/consolidator.py` | Daemon tiêu thụ staging log, thăng hạng tri thức, decay Ebbinghaus và nén dọn SQLite qua passive checkpoint. |
| **PreInvocation Hook** | `scripts/hook_runner.py` | Cổng chặn kiểm duyệt cưỡng chế & nạp JIT phản xạ L1 trong <25ms trước mỗi lượt chat. |
| **Spec-Driven Development** | `skills/spec-driven-development/` | Kỹ năng chuẩn hóa 10 phase GitHub Spec Kit SDD (Constitution, Spec, Plan, Tasks, Implement...). |
| **Dual-Tier Router** | `scripts/dual_tier.py` | Tính điểm độ phức tạp (0-100), áp dụng Quota Guard cho task đơn giản và ủy nhiệm L2 Strategist. |
| **Weekly Reporter** | `scripts/reporter.py` | Tổng hợp KPI vận hành, ước tính token tiết kiệm, thống kê tỷ lệ phân tầng và sức khỏe hệ thống. |
| **Workspace Assimilator** | `scripts/assimilator.py` | Đồng hóa không phá hủy các quy tắc `.cursorrules`, `GEMINI.md`, `CLAUDE.md`, và `.specify/` của repo. |
| **Kernel Synchronizer** | `scripts/kernel_sync.py` | Tự động phát hiện và vá lỗi lệch phiên bản (Version Drift) giữa Workspace, Plugins và Library. |

---

## 🧪 Kiểm thử Tự động Toàn diện & Chứng nhận Council Gate

Omni-Kernel v4.1 duy trì bộ kiểm thử tự động toàn diện với **100% tỷ lệ đỗ (277/277 Tests PASS: 117 pytest suites + 160 remediation verification tests)** cùng chứng nhận **`APPROVED`** có chữ ký HMAC-SHA256 hợp lệ từ DeepSeek-V4.1-Flash Council Gate ([`docs/audits/omni_kernel_v41_final_approved_verdict.md`](docs/audits/omni_kernel_v41_final_approved_verdict.md)):

```bash
# 1. Kiểm thử Lõi Động cơ, Bộ nhớ Đa tầng & Cổng Giám sát (117 tests qua pytest)
python -m pytest tests/ specs/001-omni-memory-v4/tests/ specs/002-deepseek-v41-auditor/tests/

# 2. Kiểm thử Khắc phục Chuyên sâu Cluster 1–3 & Round 7–9 (160 tests)
python scripts/test_cluster_1_remediation.py   # 69/69 passed (SQLite WAL, Outbox 2PC, SHA-256 Partitioning)
python scripts/test_cluster_2_remediation.py   # 51/51 passed (Hook <25ms SLA, HMAC Gate, Trust Lock, Lifecycle Epoch)
python scripts/test_cluster_3_remediation.py   # 17/17 passed (Resolver, AST Sandbox, CoW Stale-While-Revalidate)
python scripts/test_round_7_remediation.py     # 23/23 passed (Tích hợp Liên cụm, Proven Recall & Edge Cases)
```

---

## 🤝 Triết lý Kỹ thuật: Nền tảng Ponytail

Omni-Kernel v4.1 tuân thủ tuyệt đối **Triết lý Kỹ sư Ponytail (Tối giản & Đáng tin cậy)**:
* **Dòng code tốt nhất là dòng code không cần phải viết.** Giải pháp hoàn chỉnh nhỏ gọn nhất luôn chiến thắng.
* **Lõi Python Standard Library thuần túy cho Kernel**: Kernel, Gatekeeper Hook, và chỉ mục tìm kiếm SQLite FTS5 có **0 phụ thuộc ngoài** (`os`, `sqlite3`, `urllib`, `re`, `json`). Thư viện ngoài (ONNX) chỉ được dùng tùy chọn để tăng tốc tìm kiếm vector ở Tier 2.
* Bất biến là ưu tiên, báo lỗi rõ ràng kèm ngữ cảnh, tuyệt đối không âm thầm nuốt ngoại lệ.
* Bơm ngữ cảnh tạm thời (JIT Ephemeral) thay vì nhồi nhét quy tắc tĩnh gây ô nhiễm context.

---

## 📄 Giấy phép

Phát hành theo giấy phép MIT License. Xem chi tiết tại [LICENSE](LICENSE).
