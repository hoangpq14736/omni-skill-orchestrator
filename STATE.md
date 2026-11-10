# 🧭 Omni-Kernel & Skill Management: State Anchor (STATE.md)

> **File này là "Neo Trạng Thái Liên Phiên" (Cross-Session State Anchor).**  
> Khi bạn mở một phiên chat mới tại thư mục này, AI chỉ cần đọc file này trong 0.05 giây là có lại 100% bối cảnh đã, đang và sẽ làm gì — không bao giờ bị mất trí nhớ hay loãng context!

---

## 📌 1. Thông Tin Không Gian Làm Việc (Workspace)
- **Tên Workspace**: `Skill management`
- **Đường dẫn**: `d:\Antigravity\Skill management`
- **Vai trò**: **Trụ sở Chỉ huy Tối cao của Omni-Kernel v4.2 & Quản lý Thư viện Kỹ năng AI**.
- **Phiên bản hiện tại**: **Omni-Kernel v4.2.0 Tri-Worker Fleet** (Tích hợp trọn vẹn: Spec 001 Tri-Tier Memory + Spec 002 DeepSeek Gatekeeper 1M + Spec 003 Omni-Graph + Spec 004 Tri-Worker Fleet & SDD 1M Context).
- **Trạng thái Git**: Đồng bộ giữa Local Workspace và Global Plugin (`C:\Users\vuhuu\.gemini\config\plugins\omni-skill-orchestrator\`).
- **Tổng số Skill trong thư viện**: **517+ skills** (Đã đồng bộ và đánh chỉ mục trong `scripts/registry.json`).
- **Hệ thống Kiểm thử tự động**:
  - WAL Multi-Process Concurrency Test (NT/Windows): `PASS 100% (0 database is locked)`
  - Kernel Sync Immune System: `100% ALIGNED`
  - Gemini Cloud Worker Live Test: `PASS (2.0s turnaround)`
  - Gemini Worker JSON-RPC 2.0 Stdio Handshake: `PASS`

---

## 🤖 2. Phân Công Hạm Đội Công Nhân Kép & Cổng Kiểm Duyệt (Tri-Worker Fleet)

Theo Kernel Ring 0 Invariants: Cloud Model trong chat chỉ đóng vai trò Kiến trúc sư (Architect) và Cổng Điều phối. Toàn bộ tác vụ nặng được phân luồng tự động:
1. **`local_worker_mi50` (AMD Instinct MI50 16GB HBM2 @ 1024 GB/s)**:
   - Backend: Cục bộ qua `http://127.0.0.1:8080/v1` (`Qwen2.5-Coder-14B-Instruct-abliterated`).
   - Tác vụ: Sửa file tại chỗ (`fast_edit`), thực thi logic ngoại tuyến (`execute_code_task`), truy cập SQLite WAL, IPC mutex. Chi phí 0đ, bảo mật Ring 0 tuyệt đối.
2. **`groq_worker_cloud` (Groq LPU Cloud @ 300-800+ tok/s)**:
   - Backend: Groq Cloud MCP (`openai/gpt-oss-120b`).
   - Tác vụ: Sinh code tốc độ cực cao (`groq_code_gen`), biến đổi AST/regex, sinh hàng loạt unit test với độ trễ dưới 1 giây.
3. **`gemini_worker_cloud` (Google Gemini Cloud Heavy Worker - Quỹ 10$/tháng)**:
   - Backend: Server stdio JSON-RPC MCP tại `D:\Antigravity\Gemini Worker\gemini_worker_mcp.py` và CLI `scripts/gemini_worker.py`.
   - Tác vụ:
     - `gemini_heavy_code_gen`: Sinh mã module lớn (>32K context), refactor đa file với cửa sổ **1.000.000 tokens** (`gemini-3.5-flash-lite` / `gemini-3.8-flash`).
     - `gemini_multimodal_vision`: Đọc và bóc tách trực tiếp mockup UI, screenshot lỗi, sơ đồ kiến trúc, PCB layout.
     - `gemini_argon_solve`: Chuyên trị bài toán hóc búa, chứng minh thuật toán phức tạp qua `gemini-4-argon` suy luận sâu (`thinking: true`).
4. **`deepseek_worker_cloud` (DeepSeek-V4.1-Flash Gatekeeper - 1M Context)**:
   - Backend: Cloud REST API qua `scripts/consult_critic.py` (HMAC-SHA256 verified).
   - Tác vụ: **Hội đồng Phản biện Độc lập Tối cao (Council Protocol)**, red-teaming RFC/FRC specifications, rà soát lỗ hổng logic gắt gao. Giữ nguyên 100% để chống "Echo Chamber" (Gemini tự review Gemini).

---

## ✅ 3. Những Gì Đã Hoàn Thành (Milestones Reached)

### A. Spec 004: Tri-Worker Fleet & SDD 1M Context Upgrade (VỪA HOÀN TẤT)
- **Động cơ CLI Worker (`scripts/gemini_worker.py`)**: 100% Python Standard Library, không phụ thuộc pip, tải `GEMINI_API_KEY` an toàn từ `.env`, tự động exponential backoff + jitter, hỗ trợ tham số `--out` để chống tràn context (Zero-Context Leaking).
- **Máy chủ MCP Server (`D:\Antigravity\Gemini Worker\gemini_worker_mcp.py`)**: Triển khai đầy đủ giao thức JSON-RPC 2.0 stdio, đăng ký 3 công cụ: `gemini_heavy_code_gen`, `gemini_multimodal_vision`, `gemini_argon_solve`.
- **Cấu hình Hệ thống Antigravity (`mcp_config.json`)**: Đăng ký `gemini_worker_cloud` với quyền auto-approve.
- **Tối ưu L1 Reflex Hook (`scripts/hook_runner.py`)**: Tự động nhận diện và phân luồng Tri-Worker Fleet ngay trong Pre-Flight Reflex (<0.3ms).
- **Nâng cấp Spec-Driven Development (`skills/spec-driven-development/SKILL.md`)**:
  - Phase 5 (`council_gate`): Mở rộng tiếp nhận toàn bộ dự án với 1.000.000 tokens context của DeepSeek-V4.1-Flash.
  - Phase 7 (`implement`): Phân quyền ủy thác rõ ràng cho cả 3 worker, phá vỡ điểm nghẽn context nhỏ khi triển khai module lớn.
- **Đồng bộ Hiến pháp v4.2.0 (`rules/AGENTS.md` & `scripts/kernel_sync.py`)**: 100% các file quy tắc và kỹ năng đã được gắn kết đồng nhất.

### B. Spec 003: Omni-Graph (Graphify-Grade Codebase Topology & Contract Guard)
- **Zero-Conflict Duality**: Tách bạch vật lý giữa `omni_memory.db` và `.omni/codebase_graph.db`.
- **SQLite WAL Storage**: Các bảng `nodes`, `signatures`, `edges`, `lifecycle_hooks`, `codebase_files_meta` với 7 chỉ mục B-Tree.
- **Universal Polyglot Extractor**: 100% Python stdlib, bóc tách Python, TS/JS, Go, Rust, SQL, Shell, Markdown.
- **Hardened Signature Contract Guard & Lifecycle Guard**: Chuẩn hóa method receiver, bắt lỗi PEP 570, keyword-only, unawaited async.
- **Interactive Vis.Network 9.1.6 Visualizer**: Tự động ổn định (Zero perpetual motion), Fermat spiral seed, Sidebar Graphify đầy đủ.

### C. Spec 002: Giám Sát Kiến Trúc Độc Lập Omni-Auditor v4.1 (DeepSeek Gatekeeper)
- Triệt tiêu hoàn toàn sự phụ thuộc vào trình duyệt (`consult_argon.py`), thay bằng kết nối Cloud API trực tiếp (`scripts/consult_critic.py`).
- Cấm tiệt hiện tượng buồng vang tự kỷ (Antigravity tự sinh subagent Gemini để tự review chính mình).
- Zero-dependency REST client viết bằng 100% Python stdlib (`urllib.request`).
- Server JSON-RPC 2.0 stdio MCP đặt tại `d:\Antigravity\DeepSeek Worker\deepseek_worker_mcp.py`.

### D. Spec 001: Tri-Tier Omni-Memory v4.1 (Episodic Memory Hierarchy)
- **Tier 1 (L1 Reflex - <25ms Turnaround, <0.3ms Reflex)**: Ephemeral PreInvocation hook trong `scripts/hook_runner.py` (100% Python stdlib). Spool phi khóa `l1_staging_spool.jsonl`.
- **Tier 2 (L2 Hybrid Memory - <15ms Retrieval)**: SQLite WAL (`omni_memory.db`), FTS5 BM25 + CPU ONNX Embeddings 256 chiều (`google/embeddinggemma-2-omni` INT8 MRL) qua RRF ($k=20$).
- **Tier 3 (L3 Background Consolidator)**: Daemon `scripts/consolidator.py` tiêu thụ log staging, thăng hạng tri thức ($\ge 2$ lần), tính độ suy giảm Ebbinghaus.

---

## 🚀 4. Trạng Thái Hiện Tại & Bước Kế Tiếp

### Trạng Thái Hiện Tại:
- **Lõi Omni-Kernel v4.2 Tri-Worker Fleet**: Đã triển khai và kiểm thử thành công 100%.
- **Sẵn sàng Nhận việc**: Cả 3 workers (`local_worker_mi50`, `groq_worker_cloud`, `gemini_worker_cloud`) và Gatekeeper (`deepseek_worker_cloud`) đều đã vào vị trí chiến đấu.

### Các Đề Mục Sẵn Sàng Thực Hiện Tiếp Theo:
1. Thực hiện các dự án lập trình thực tế sử dụng quy trình SDD 10 pha với Tri-Worker Fleet.
2. Trực quan hóa cấu trúc nâng cao: D3 Collapsible Tree Visualizer (`tree.html`) cho Omni-Graph.
