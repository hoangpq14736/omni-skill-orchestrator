# 🧠 Omni-Skill Orchestrator v4.1: Lớp Điều Phối Kỹ Năng JIT & Bộ Nhớ Phản Xạ Cho Tác Tử AI

[![Agent Plugins 1.0.0](https://img.shields.io/badge/Spec-Agent%20Plugins%201.0.0-blue.svg)](https://agent-plugins.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)
[![Zero Dependency Kernel](https://img.shields.io/badge/Dependencies-0%20(Lõi%20Stdlib%20Thuần%20Túy)-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-277%2F277%20Passing-success.svg)]()
[![Council Gate](https://img.shields.io/badge/DeepSeek%20Council%20Gate-APPROVED-brightgreen.svg)](docs/audits/omni_kernel_v41_final_approved_verdict.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) • [Tiếng Việt](README.vi.md)

> **Lớp điều phối (harness) siêu nhẹ, vận hành cục bộ (local-first) dành cho Google Antigravity, Claude Code, Cursor và các AI coding agent.**  
> *Trang bị cơ chế định tuyến kỹ năng JIT tốc độ dưới mili-giây, kiến trúc trí nhớ đa tầng Tri-Tier (SQLite WAL + Dual-Column FTS5 BM25 + CPU ONNX Embeddings 384 chiều), tự động tổng hợp kỹ năng mới, và cổng kiểm duyệt kiến trúc độc lập — với 0 token tĩnh lãng phí.*

---

## 🎯 Omni-Skill Orchestrator thực sự là gì?

Omni **không phải** là một tác tử lập trình độc lập (như Aider, OpenCode hay OpenHands). Thay vào đó, Omni đóng vai trò là một **lớp điều phối và phản xạ tiền khởi chạy (Pre-flight Harness & Reflex Layer)** bọc ngoài mô hình chính của bạn (như Antigravity, Claude Code):

1. **Chống phình to ngữ cảnh (Context Bloat)**: Thay vì nhồi 50–120 kỹ năng và quy tắc tĩnh vào System Prompt (ngốn 15.000–25.000 token mỗi lượt chat), Omni quét hơn 500 kỹ năng trong **0.12s** và chỉ tiêm 1–3 kỹ năng/quy tắc phù hợp nhất **Đúng Lúc (Just-In-Time, < 300 token)**.
2. **Trí nhớ phản xạ đa phiên (Cross-Session Memory)**: Tự động ghi nhận các giải pháp sửa lỗi thành công, đánh chỉ mục vào SQLite WAL với FTS5 BM25 và vector đặc ONNX CPU 384 chiều (`intfloat/multilingual-e5-small`), gợi ý lại giải pháp đã kiểm chứng trong **< 0.3ms**.
3. **Tự tổng hợp kỹ năng mới (Autonomous Skill Synthesis)**: Khi đối mặt với công nghệ lạ chưa có trong thư viện, Omni tự soạn thảo file `SKILL.md`, quét tĩnh AST kiểm tra an toàn, chạy kiểm thử trong sandbox và tự động thăng hạng vào thư viện cục bộ.
4. **Cổng kiểm duyệt kiến trúc độc lập (Council Gate)**: Phát hiện các yêu cầu thiết kế hệ thống lớn (RFC, SDD, diff lớn) trong `< 25ms` logic nội bộ (`~120ms` toàn tiến trình subprocess trên Windows) mà không làm tắc nghẽn phiên chat bằng các lệnh gọi mạng đồng bộ.

---

## ⚡ So sánh Tính năng Thực tế

| Tiêu chí | Nhồi Kỹ năng Tĩnh Truyền thống | Omni-Skill Orchestrator v4.1 |
|---|---|---|
| **Dung lượng Ngữ cảnh** | Nhồi 50–120 kỹ năng (**15.000–25.000 token**), gây tràn ngữ cảnh và suy giảm IQ mô hình. | **< 300 Token ở trạng thái chờ!** Giữ nguyên tắc tinh gọn; kỹ năng, quy tắc và công cụ được phân giải Đúng Lúc (JIT). |
| **Độ chính xác Định tuyến** | So khớp chuỗi con thô sơ dễ gọi nhầm sang kỹ năng không liên quan. | **Chấm điểm theo Segment + Ranh giới Từ**: Tách biệt rõ nhóm từ miền kỹ thuật (`docker`, `sqlite`, `postgres`) khỏi từ hành động chung (`fix`, `debug`, `guide`). Đạt **100% Top-1 & Top-3** trên bộ Golden Benchmark 25 câu hỏi. |
| **Trí nhớ Dài hạn** | File JSON phẳng dễ hỏng hoặc vector DB SaaS đám mây cồng kềnh. | **Trí nhớ Đa tầng Tri-Tier**: Tầng 1 non-blocking RAM spool (<0.3ms); Tầng 2 SQLite WAL nhúng FTS5 BM25 + CPU ONNX Embeddings (0MB VRAM Tax); Tầng 3 Consolidator tự động tính độ trôi dạt Ebbinghaus. |
| **Tổng hợp Kỹ năng** | Lập trình viên phải tự gõ thủ công từng file cấu hình cho mỗi thư viện mới. | **Quy trình Tự động**: `scripts/synthesizer.py` tự tạo mẫu, kiểm tra cú pháp AST, kiểm chứng assert trong sandbox và tự tái lập chỉ mục trong <150ms. |
| **Kiểm soát Kiến trúc** | Subagent nội bộ dễ rơi vào "Buồng vang tự sướng" (Echo Chamber), tự khen code của nhau. | **Hội đồng Phản biện Độc lập (DeepSeek-V4.1-Flash)**: Cưỡng chế kiểm duyệt với chữ ký số HMAC-SHA256 và mã băm SHA-256 của file đích mà không làm nghẽn luồng hook. |
| **Lõi Phụ thuộc** | Phụ thuộc thư viện nặng ngoài luồng, dễ lỗi môi trường. | **Lõi Python Standard Library thuần túy** cho Kernel, Hook và SQLite FTS5 (0 phụ thuộc ngoài). Tùy chọn cài thêm `fastembed` cho tìm kiếm vector CPU (tự động hạ cấp an toàn về FTS5 BM25 nếu chưa cài). |

---

## 🏗️ Kiến trúc Phân tầng

Omni vận hành như một bộ cương đánh chặn bọc quanh tác tử AI:

```text
                      ┌────────────────────────────────────────────────────────┐
                      │              AI AGENT: ANTIGRAVITY / CLAUDE            │
                      │               (Lập kế hoạch, UI, Viết code)            │
                      └───────────────────────────┬────────────────────────────┘
                                                  │ (Trước mỗi lượt tương tác)
                                                  ▼
                      ┌────────────────────────────────────────────────────────┐
                      │    PRE-FLIGHT HARNESS HOOK (hook_runner.py, <25ms)     │
                      │  - Tầng 1: Phản xạ RAM không nghẽn lock (<0.3ms)       │
                      │  - JIT Router: Phân giải kỹ năng theo segment (~2-5ms) │
                      │  - Truy hồi Ký ức Thực nghiệm độ chính xác cao (<0.3ms)│
                      │  - Cổng Giám sát: Đối chiếu chữ ký số HMAC-SHA256      │
                      └───────────────────────────┬────────────────────────────┘
                                                  │ (Tiêm <300 token ngữ cảnh JIT)
                                                  ▼
                                      ┌───────────────────────┐
                                      │   LƯỢT CHAT CỦA AGENT │
                                      └───────────────────────┘
```

---

## 🧠 Kiến trúc Trí nhớ Đa tầng Tri-Tier Omni-Memory

Toàn bộ giải pháp khắc phục lỗi và dấu vết thực thi được quản trị qua 3 tầng:

1. **Tier 1 (L1 Ephemeral Reflex - <0.3ms cache reflex, <25ms logic hook nội bộ / ~120ms subprocess)**:
   - Hook tiền khởi chạy viết bằng 100% Python Standard Library trong `scripts/hook_runner.py`.
   - Đọc bộ đệm RAM nhanh từ `scripts/proven_traces.json` trong <0.02ms.
   - Ghi nhật ký non-blocking vào `l1_staging_spool.jsonl` để loại trừ hoàn toàn hiện tượng tranh chấp khóa SQLite trên Windows NTFS.

2. **Tier 2 (L2 Hybrid Episodic Memory - <15ms retrieval, 0MB VRAM Tax)**:
   - Cơ sở dữ liệu SQLite nhúng tại `omni_memory.db` kích hoạt chế độ **WAL mode** (`PRAGMA synchronous = NORMAL;`, `busy_timeout = 5000;`).
   - Tìm kiếm hỗn hợp kết hợp **Dual-Column FTS5 BM25** (`content_exact` trọng số 10.0 vs `content_folded` trọng số 1.0) song song với **CPU ONNX Embeddings** (`intfloat/multilingual-e5-small`, 384 chiều, INT8 quantization, 0MB VRAM) qua thuật toán Reciprocal Rank Fusion ($k=20$).
   - *Cơ chế Hạ cấp An toàn:* Nếu môi trường chưa cài `fastembed`, hệ thống tự động fallback về chế độ 100% thuần stdlib SQLite FTS5 BM25.

3. **Tier 3 (L3 Background Consolidator Daemon)**:
   - Tiến trình chạy ngầm `scripts/consolidator.py` tiêu thụ các bản ghi từ spool vào cơ sở dữ liệu.
   - Tự động thăng hạng vết tri thức đa kích hoạt ($\ge 2$ lần thành công) kèm gán nhãn song ngữ tự động.
   - Áp dụng công thức suy giảm ổn định Ebbinghaus và sử dụng `PRAGMA wal_checkpoint(PASSIVE);` để chống hoàn toàn xung đột khóa file.

---

## 🛠️ Danh mục Module Cốt lõi

| Thành phần | Đường dẫn | Mô tả chức năng |
|---|---|---|
| **PreInvocation Hook** | `scripts/hook_runner.py` | Cổng chặn kiểm duyệt tiền khởi chạy, nạp JIT kỹ năng, quy tắc và trí nhớ (<25ms nội bộ, ~120ms subprocess). |
| **JIT Skill Resolver** | `scripts/resolver.py` | Động cơ định tuyến kỹ năng theo segment (<5ms warm, word-boundary, chế tài theo domain). |
| **Autonomous Synthesizer** | `scripts/synthesizer.py` | Pipeline tự động tạo mẫu, kiểm tra cú pháp AST, chạy thử sandbox và thăng hạng kỹ năng mới. |
| **Skill Indexer** | `scripts/indexer.py` | Bộ lập chỉ mục tốc độ cao quét 500+ kỹ năng qua 4 nguồn trong 0.12s với khả năng phát hiện thay đổi ở cấp mili-giây. |
| **Experiential Memory** | `scripts/experiential_memory.py` | Kho lưu trữ vết thực thi với bộ lọc từ dừng và tốc độ truy hồi dưới 1 mili-giây. |
| **Memory Engine** | `scripts/memory_engine.py` | Lõi tìm kiếm bộ nhớ hỗn hợp SQLite FTS5 BM25 + ONNX Dense Vector Embeddings qua RRF. |
| **Embedding Service** | `scripts/embedding_service.py` | Dịch vụ sinh vector embedding cục bộ trên CPU bằng `fastembed` (`intfloat/multilingual-e5-small`, 384 chiều). |
| **Memory Consolidator** | `scripts/consolidator.py` | Daemon tiêu thụ staging log, thăng hạng tri thức và tính toán độ suy giảm Ebbinghaus. |
| **Architecture Auditor** | `scripts/consult_critic.py` | Client kết nối DeepSeek-V4.1-Flash phản biện kiến trúc độc lập. |

---

## 🧪 Kiểm thử Tự động & Chứng thực Thực nghiệm

Omni-Skill Orchestrator duy trì bộ kiểm thử tự động toàn diện với **100% tỷ lệ đỗ (277/277 Tests PASS, 0 Skipped, 0 Flaked)**:

```bash
# 1. Chạy toàn bộ pytest lõi và spec test suites (117 tests, 0 skipped)
python -m pytest tests/ specs/001-omni-memory-v4/tests/ specs/002-deepseek-v41-auditor/tests/

# 2. Chạy 4 bộ kiểm thử khắc phục Cluster 1–3 & Round 7 (160 tests)
python scripts/test_cluster_1_remediation.py   # 69/69 passed (SQLite WAL, Outbox 2PC, Phân vùng SHA-256)
python scripts/test_cluster_2_remediation.py   # 51/51 passed (SLA Hook <25ms, Cổng HMAC, Trust Lock)
python scripts/test_cluster_3_remediation.py   # 17/17 passed (Resolver, Sandbox AST, CoW Stale-While-Revalidate)
python scripts/test_round_7_remediation.py     # 23/23 passed (Tích hợp Liên cụm, Proven Recall & Edge Cases)

# 3. Chạy Hợp đồng 10 Kịch bản Thực tế, Đánh giá Golden Routing 25 Câu & Đo Benchmark Thật
python scripts/verify_real_world.py
# Kết quả: 10/10 Kịch bản PASS | Golden Routing Top-1 = 25/25 (100%), Top-3 = 25/25 (100%)
# Độ trễ thật: Resolver warm: ~2-5ms | Hook core: ~12-22ms | SQLite FTS5: ~0.3-0.5ms
```

---

## 📄 Giấy phép

Phát hành theo giấy phép MIT License. Xem chi tiết tại [LICENSE](LICENSE).
