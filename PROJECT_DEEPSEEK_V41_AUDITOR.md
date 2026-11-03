# 🚀 Project Blueprint: Omni-Auditor v4.1
## Tích hợp DeepSeek-V4.1-Flash làm Giám sát viên Kiến trúc & Cổng Kiểm duyệt Gắt gao (Strict Architecture Gatekeeper)

> **File này là Blueprint Khởi động (Kickstart Project Specification)** cho phiên làm việc mới tại thư mục `d:\Antigravity\Skill management`.  
> Khi khởi động phiên mới, AI chỉ cần đọc tài liệu này để nắm bắt 100% bối cảnh, lý do thiết kế, cấu trúc kỹ thuật và lộ trình thực thi mà không cần giải thích lại từ đầu.

---

## 📌 1. Bối cảnh & Bài toán cần giải quyết (Problem Statement)

### Hiện trạng hệ thống (Omni-Kernel v3.0 / v4.0 Fleet):
* **Chỉ huy trưởng:** Google Antigravity (Gemini 2.5/3.x Pro & Flash) điều phối qua Omni-Kernel.
* **Worker Fleet hiện có:**
  * `local_worker_mi50` (AMD Instinct MI50 16GB HBM2 @ 1024 GB/s): Chuyên trách local file edit, SQLite WAL, zero-latency, 100% offline.
  * `groq_worker_cloud` (Groq LPU @ 300–800 tok/s): Chuyên nhả boilerplate, regex, AST parsing, unit test stubs siêu tốc.

### Vấn đề thực tế đã phát hiện (từ phiên làm việc `458dac80-8d90-4eef-ac33-c70e4aa95e4c`):
1. **Điểm nghẽn Argon Bridge (Tampermonkey):**
   * Cơ chế cũ dùng `consult_argon.py` kết nối sang web chat Gemini thông qua Tampermonkey local bridge (`http://127.0.0.1:7890`).
   * Phụ thuộc vào việc người dùng phải mở tab trình duyệt, dễ bị đứt phiên, dính CAPTCHA, và độ trễ cao (timeout 240s).
2. **Hiện tượng "Buồng vang tự kỷ" (Echo Chamber):**
   * Khi gọi `/teamwork` để soạn thảo FRC/SDD, Antigravity **hoàn toàn bỏ qua việc gọi Argon**, cũng không gọi Worker.
   * Thay vào đó, AGY tự đẻ ra các subagent (Reviewer, Challenger, Forensic Auditor). Vì tất cả các subagent này đều chạy chung một mô hình Gemini, hệ thống tự tranh luận với chính mình, che giấu các "điểm mù" (blind spots) về mặt kiến trúc.
3. **Cơ chế "Nhắc nhở mềm" (Soft Prompting) thất bại:**
   * Việc chỉ ghi luật vào `rules/AGENTS.md` khiến LLM dễ dàng lờ đi để chọn con đường ngắn nhất (Path of Least Resistance).

---

## 🎯 2. Giải pháp: Tam quyền Phân lập với DeepSeek-V4.1-Flash

Thay vì thêm thợ gõ code làm loãng hệ thống, **DeepSeek-V4.1-Flash** (phiên bản kiến trúc MoE 552B mới nhất cuối 2026 với bản vá `-1017`) được biên chế vào vị trí **Tổng Giám Sát Kiến Trúc Độc Lập (Strict Architecture Gatekeeper)**.

### Tại sao chọn DeepSeek-V4.1-Flash (2026) thay vì R1 (2025)?
1. **Cửa sổ ngữ cảnh 1 Triệu Tokens (1M Context Window):** Nuốt trọn toàn bộ codebase, PRD, RFC, Constitution và test suite trong 1 lần gọi (R1 cũ chỉ 64k tokens).
2. **Native Agentic Tuning (`-1017`):** Được huấn luyện sâu cho môi trường Agent Harness (DSH, Claude Code, Mini-SWE); hiểu cấu trúc SDD và format diff chuẩn xác.
3. **MoE Siêu tốc & Giá rẻ:** Kích hoạt chỉ 8B/16B token, phản hồi trong vài giây với mức giá ~$0.30/1M input tokens.
4. **Đa phương thức bản địa:** Đọc hiểu trực tiếp sơ đồ kiến trúc, UI layout và workflow diagram.

---

## 🏗️ 3. Mô hình Kiến trúc Phân tầng Mới

```
                               ┌────────────────────────────────────────────────────────┐
                               │       CHỈ HUY TRƯỞNG: ANTIGRAVITY (Omni-Kernel)        │
                               │        (Lập kế hoạch, Quản lý tiến trình, UI)          │
                               └───────────────────────────┬────────────────────────────┘
                                                           │
                                                           ▼
                           ┌────────────────────────────────────────────────────────────┐
                           │          HARD GATEKEEPER HOOK (hook_runner.py)             │
                           │  [Cưỡng chế chặn mọi bản RFC / FRC / Diff lớn trước khi commit]│
                           └───────────────────────────────┬────────────────────────────┘
                                                           │ (Bắt buộc qua Gate)
                                                           ▼
                                           ┌────────────────────────────────┐
                                           │    DEEPSEEK-V4.1-FLASH AUDITOR │
                                           │   (Mô hình phản biện độc lập)  │
                                           │    - 1M Context Window         │
                                           │    - Red-Teaming Persona       │
                                           │    - Direct Cloud REST API     │
                                           └────────────────┬───────────────┘
                                                            │
                                  ┌─────────────────────────┴─────────────────────────┐
                                  ▼                                                   ▼
                         [NẾU REJECT / LỖI]                                    [NẾU APPROVED]
                                  │                                                   │
                                  ▼                                                   ▼
                      Trả về danh sách phản biện                               Giao việc cho Worker
                      Yêu cầu Planner tinh chỉnh lại                                  │
                                                                 ┌────────────────────┴────────────────────┐
                                                                 ▼                                         ▼
                                                       ┌──────────────────┐                      ┌──────────────────┐
                                                       │ groq_worker_cloud│                      │local_worker_mi50 │
                                                       │ (Groq LPU 120B)  │                      │ (AMD MI50 16GB)  │
                                                       │ Sinh code & test │                      │ Ghi đĩa & SQLite │
                                                       │ chớp nhoáng      │                      │ 100% offline     │
                                                       └──────────────────┘                      └──────────────────┘
```

---

## 🛠️ 4. Chi tiết các Module kỹ thuật cần xây dựng

### Module 1: `scripts/consult_critic.py` (Thay thế vĩnh viễn `consult_argon.py`)
* **Mục tiêu:** Client trực tiếp gọi DeepSeek API (`deepseek-v4.1-flash`).
* **Tính năng:**
  * Zero external dependencies (chỉ dùng Python stdlib `urllib.request`).
  * Timeout mặc định: 30s (không để treo tiến trình).
  * Hỗ trợ 2 chế độ:
    * `--mode rfc`: Soi lỗi kiến trúc, vi phạm invariant, rủi ro OOM/bảo mật trong file đặc tả.
    * `--mode code`: Soi race condition, boundary check, memory leak trong Git Diff.
  * System Prompt: **Red-Teaming Critic Persona** (Nghiêm cấm khen ngợi, tập trung 100% vào việc tìm ra ít nhất 3 rủi ro tiềm ẩn hoặc edge case).

### Module 2: `deepseek_worker_mcp.py` (Đăng ký MCP Server)
* **Vị trí:** `d:\Antigravity\DeepSeek Worker\deepseek_worker_mcp.py`
* **Công cụ xuất xưởng:**
  * `deepseek_audit_spec`: Duyệt toàn bộ bundle SDD/RFC trước khi người dùng bấm Proceed.
  * `deepseek_audit_diff`: Duyệt diff mã nguồn của Groq hoặc MI50 trước khi merge vào codebase.
* **Cấu hình:** Đăng ký vào `C:\Users\vuhuu\.gemini\config\mcp_config.json`.

### Module 3: Nâng cấp `hook_runner.py` (Deterministic Hard Gate)
* **Cơ chế:** Khi trigger phát hiện thao tác liên quan đến RFC, SDD hoặc `/teamwork`:
  * Tự động kích hoạt `consult_critic.py` ở tầng subprocess trước khi trả context về cho Gemini.
  * Chèn kết quả phản biện trực tiếp vào context prompt: `[CRITICAL REVIEW FROM DEEPSEEK-V4.1-FLASH]`.
  * AGY bắt buộc phải giải trình hoặc sửa đổi theo phản biện này, loại bỏ khả năng tự ý dùng subagent nội bộ để "tự duyệt".

### Module 4: Cập nhật `rules/AGENTS.md`
* Cập nhật Điều 5 (Council Protocol): Thay thế định danh *Gemini 4 Argon* thành *DeepSeek-V4.1-Flash Council Gate*.

---

## 📋 5. Kế hoạch Triển khai (Actionable Milestones)

| Milestone | Tác vụ cụ thể | Trạng thái |
| :--- | :--- | :--- |
| **M1: Core Client** | Viết `scripts/consult_critic.py` kết nối DeepSeek-V4.1-Flash API (Zero-dependency stdlib, Devil's Advocate persona, timeout 30s, backoff full-jitter). | ✅ Hoàn thành 100% (T010-T017) |
| **M2: MCP Tooling** | Dựng `d:\Antigravity\DeepSeek Worker\deepseek_worker_mcp.py` và cấu hình `mcp_config.json` (`deepseek_audit_spec`, `deepseek_audit_diff`). | ✅ Hoàn thành 100% (T018-T026) |
| **M3: Kernel Hard Gate** | Tích hợp cổng chặn cưỡng chế vào `hook_runner.py` (2-state verification) và cập nhật Rule 6 trong `rules/AGENTS.md`. | ✅ Hoàn thành 100% (T027-T033) |
| **M4: Validation Run** | Chạy thử nghiệm giả lập RFC/SDD flawed, kiểm tra fail-closed auth gate, zero credential leakage, 43/43 Pytest pass. | ✅ Hoàn thành 100% (T034-T040) |

---

## 🚀 6. Hướng dẫn Cho Phiên Mới (Prompt for Next Session)

Khi bạn mở một phiên chat mới tại `d:\Antigravity\Skill management`, hệ thống Omni-Kernel v4.1 và Omni-Auditor đã sẵn sàng 100%. Bạn có thể gõ:

```text
Đọc STATE.md và bắt đầu làm việc.
```
