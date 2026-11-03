# 🧭 Omni-Kernel & Skill Management: State Anchor (STATE.md)

> **File này là "Neo Trạng Thái Liên Phiên" (Cross-Session State Anchor).**  
> Khi bạn mở một phiên chat mới tại thư mục này, AI chỉ cần đọc file này trong 0.05 giây là có lại 100% bối cảnh đã, đang và sẽ làm gì — không bao giờ bị mất trí nhớ hay loãng context!

---

## 📌 1. Thông Tin Không Gian Làm Việc (Workspace)
- **Tên Workspace**: `Skill management`
- **Đường dẫn**: `d:\Antigravity\Skill management`
- **Vai trò**: **Trụ sở Chỉ huy Tối cao của Omni-Kernel v4.0 & Quản lý Thư viện Kỹ năng AI**.
- **Phiên bản hiện tại**: **Omni-Kernel v4.0.0** (Release FRC-2026-004).
- **Trạng thái Git**: Đồng bộ với `origin/main` (`hoangpq14736/omni-skill-orchestrator`), commit `3c23ae5`.
- **Tổng số Skill trong thư viện**: 504+ skills (Đã index trong `scripts/registry.json`).
- **Bộ kiểm thử tự động**: **64/64 Tests PASS (100%)** — gồm 30 Engine Tests + 34 Omni-Memory v4 Tests, chạy toàn bộ trong 2.97s.

---

## ✅ 2. Những Gì Đã Hoàn Thành (Milestones Reached)

### A. Nâng Cấp Toàn Diện Omni-Kernel v4.0 & Omni-Memory v4.0 Tri-Tier Architecture (FRC-2026-004)
- **Tri-Tier Cognitive Memory Hierarchy**:
  - **Tier 1 (L1 Reflex - <25ms Turnaround, <0.3ms Reflex)**: Ephemeral PreInvocation hook trong `scripts/hook_runner.py` viết bằng 100% Python Standard Library (Zero-Dependency), clamp input an toàn 2,048 ký tự, khử filler patterns qua boundary matching, truy vấn in-memory traces trong <0.02ms, lazy batch detaching kích hoạt consolidator trên Windows bằng `DETACHED_PROCESS` không bao giờ treo pipe stdout/stderr.
  - **Tier 2 (L2 Hybrid Memory - <15ms Retrieval)**: Database SQLite nhúng (`omni_memory.db`) kích hoạt WAL mode (`PRAGMA synchronous = NORMAL;`, `busy_timeout = 5000;`, `auto_vacuum = INCREMENTAL;`). Tìm kiếm hỗn hợp kết hợp **Dual-Column FTS5 BM25** (`content_exact` trọng số 10.0 vs `content_folded` trọng số 1.0) song song với **Topology A Host CPU ONNX Embeddings** (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions, INT8 quantization, 0 MB GPU VRAM, 7.02ms latency) thông qua thuật toán Reciprocal Rank Fusion ($k=20$).
  - **Tier 3 (L3 Background Consolidator)**: Out-of-band consolidation daemon trong `scripts/consolidator.py`. Tự động tiêu thụ bản ghi từ `l1_staging_log`, thăng hạng multi-hit patterns ($\ge 2$ lần thành công) kèm gán nhãn song ngữ tự động, áp dụng suy giảm ổn định Ebbinghaus, tự động soft-archive các bản ghi hết hạn (`status = 'Archived'`), và quản lý phiên bản quy tắc bất biến (`status = 'Superseded'`, `superseded_by`).
- **Hội đồng Thẩm định Kiến trúc Gemini 4 Argon (Council Protocol)**:
  - Cầu nối tích hợp tự động qua `scripts/consult_argon.py` và `scripts/argon_bridge.py`.
  - Bộ tài liệu lưu trữ: `docs/rfcs/RFC-004-omni-memory-v4.md`, `docs/rfcs/ARGON_CRITIQUE.md`, `docs/rfcs/ARGON_REVIEW.md`.
- **Thực thi Đặc tả SDD & Kiểm thử Chặt chẽ**:
  - Hoàn thiện 100% 6 Phase trong bundle `specs/001-omni-memory-v4/` (`constitution.md`, `spec.md`, `plan.md`, `tasks.md`).
  - Đạt 34/34 bài test Omni-Memory + 30/30 bài test Engine = **64/64 bài test tuyệt đối PASS**.
  - Đã đồng bộ 100% sang global plugin `C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\`.

### B. Nền Tảng Kế Thừa Từ Omni-Kernel v3.0
- **Dual-Tier Cognitive Routing**: Phân tầng L1 Reflex (<1ms, 0 token cho 85% tác vụ) và L2 Strategist Subagent (`omni-strategist` cho tác vụ lớn).
- **Virtual MCP Bus**: Tự động định tuyến công cụ MCP động qua `mcp_gateway.py`.
- **Non-Destructive Workspace Assimilator**: Đồng hóa quy tắc dự án từ `.cursorrules`, `GEMINI.md`, `CLAUDE.md`, `specs/`, `.specify/` trong <1ms.
- **Bộ Báo Cáo Tiến Trình & Tăng Trưởng Hàng Tuần (Weekly Reporter)**: Script `scripts/reporter.py` tự động tổng hợp KPI, ước tính token tiết kiệm, thống kê tỷ lệ phân tầng L1/L2.

### C. Tích Hợp Toàn Diện GitHub Spec Kit (Spec-Driven Development - SDD)
- Đóng gói toàn bộ 10 nguyên mẫu SDD (`constitution`, `specify`, `clarify`, `plan`, `tasks`, `implement`, `converge`, `checklist`, `analyze`, `taskstoissues`) thành **Global Skill bản địa** tại `skills/spec-driven-development/SKILL.md` và `~/.gemini/config/skills_library/`.
- Hỗ trợ **cơ chế kép (Hybrid Mode)**: Native Zero-Dependency Mode (AppLocker-safe) và CLI Mode (tương thích `specify 1.2.5`).

---

## 🔍 3. Kho Tri Thức Phân Tích (Deep-Dive Researched Repos)

1. **`github/spec-kit`**: Kiến trúc đặc tả trước khi code (SDD), cấu trúc template markdown, tích hợp Antigravity `.agents/skills/speckit-*`.
2. **`CopilotKit/openbot`**: Nền tảng Enterprise AI Coworker tự host; container Chromium riêng (`agent-computer`), Security Action Gateway với CEL rules, AG-UI và Generative UI.

---

## 🚀 4. Trạng Thái Hiện Tại & Định Hướng Tiếp Theo (Current & Next)

- **Hiện tại**: 
  - **Omni-Kernel v4.0** đã chính thức hoàn thiện, nghiệm thu và đẩy lên GitHub (`3c23ae5`).
  - Hệ thống trí nhớ đa tầng Tri-Tier Omni-Memory v4.0 đang bảo vệ và tối ưu hóa toàn bộ các turn chat trên máy.
- **Dự án Trọng điểm Tiếp theo**:
  - **Omni-Auditor v4.1**: Thay thế cơ chế Argon bridge bằng **DeepSeek-V4.1-Flash** làm Giám sát viên Kiến trúc & Cổng kiểm duyệt gắt gao (Strict Architecture Gatekeeper), kết hợp cùng Groq Worker và Local MI50.
  - Toàn bộ đặc tả, lý do thiết kế và 4 Milestone thực thi đã được ghi nhận tại [`PROJECT_DEEPSEEK_V41_AUDITOR.md`](file:///d:/Antigravity/Skill%20management/PROJECT_DEEPSEEK_V41_AUDITOR.md).
- **Định hướng chung**:
  - Khi cần khảo sát, phân tích repo mới hoặc đóng gói kỹ năng mới $\rightarrow$ Làm việc trực tiếp tại workspace này.
  - Khi bắt tay vào code dự án cụ thể $\rightarrow$ Mở một phiên riêng tại thư mục của dự án đó, dùng lệnh `/speckit-specify` để khởi động dự án theo chuẩn SDD.

---

## 💡 Lời Nhắc Cho Phiên Mới (Prompt for New Session)
Khi mở một phiên mới toanh tại thư mục này, bạn chỉ cần gõ:
> *"Đọc `STATE.md`, tôi muốn [yêu cầu mới, ví dụ: kiểm tra kỹ năng X / phân tích repo Y / cập nhật Z]"*
