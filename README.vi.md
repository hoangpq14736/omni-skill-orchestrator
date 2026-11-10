# ⚡ Omni-Skill Orchestrator v4.3: Lớp Điều Phối Kỹ Năng JIT, Hạm Đội Tri-Worker & Bộ Nhớ Phản Xạ

[![Agent Plugins 1.0.0](https://img.shields.io/badge/Spec-Agent%20Plugins%201.0.0-blue.svg)](https://agent-plugins.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)
[![Zero Dependency Kernel](https://img.shields.io/badge/Dependencies-0%20(Lõi%20Stdlib%20Thuần%20Túy)-brightgreen.svg)]()
[![Council Gate](https://img.shields.io/badge/DeepSeek%20Council%20Gate-APPROVED%20(1M%20Context)-brightgreen.svg)](docs/audits/omni_kernel_v41_final_approved_verdict.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) • [Tiếng Việt](README.vi.md)

> **Lớp điều phối (harness) siêu nhẹ, vận hành cục bộ (local-first) dành cho Google Antigravity, Claude Code, Cursor và các AI coding agent.**  
> *Trang bị cơ chế định tuyến kỹ năng JIT tốc độ dưới mili-giây, Hạm đội Tri-Worker tự động phân luồng (Local MI50 + Groq 120B LPU + Gemini Heavy Cloud 1M), kiến trúc trí nhớ đa tầng Tri-Tier (SQLite WAL + Dual-Column FTS5 BM25 + CPU ONNX Embeddings 384 chiều), đồ thị cấu trúc codebase chuẩn Graphify (Omni-Graph), và cổng kiểm duyệt kiến trúc độc lập DeepSeek-V4.1-Flash (1M context) — với 0 token tĩnh lãng phí.*

> [!WARNING]
> ### ⚠️ Dự Án Cá Nhân Đo Ni Đóng Giày (Personal Tailor-Made Project)
> Repository này là dự án cá nhân được thiết kế và tùy biến riêng biệt ("đo ni đóng giày") 100% cho tác giả, gắn liền với hạ tầng phần cứng cụ thể (AMD Instinct MI50 16GB, Groq LPU, hạn mức Google Cloud API, đường dẫn Windows NTFS cục bộ) và thói quen làm việc riêng. Dự án **KHÔNG dành cho cộng đồng, không hỗ trợ cài đặt hay phục vụ mục đích sử dụng chung**. Vui lòng không sao chép hoặc cố gắng cài đặt nếu không có cùng hạ tầng phần cứng và môi trường đặc thù.

---

## 🎯 Omni-Skill Orchestrator thực sự là gì?

Omni **không phải** là một tác tử lập trình độc lập (như Aider, OpenCode hay OpenHands). Thay vào đó, Omni đóng vai trò là một **lớp điều phối và phản xạ tiền khởi chạy (Pre-flight Harness & Reflex Layer)** bọc ngoài mô hình chính của bạn (như Antigravity, Claude Code):

1. **Chống phình to ngữ cảnh (Context Bloat)**: Thay vì nhồi 50–120 kỹ năng và quy tắc tĩnh vào System Prompt (ngốn 15.000–25.000 token mỗi lượt chat), Omni quét hơn 500 kỹ năng trong **0.12s** và chỉ tiêm 1–3 kỹ năng/quy tắc phù hợp nhất **Đúng Lúc (Just-In-Time, < 300 token)**.
2. **Giao thức Hạm Đội Ba Công Nhân (Tri-Worker Fleet Protocol)**: Tự động phân luồng tác vụ ngầm phía sau hậu trường để bảo tồn ngữ cảnh đám mây:
   - **`local_worker_mi50`** (AMD Instinct MI50 16GB HBM2 @ 1024 GB/s): Xử lý logic ngoại tuyến, sửa file tại chỗ (`fast_edit`), giao dịch SQLite WAL, khóa IPC mutex.
   - **`groq_worker_cloud`** (Groq LPU @ 300–800+ tok/s): Sinh mã boilerplate tức thì, biến đổi AST/regex, sinh hàng loạt bộ kiểm thử đơn vị với độ trễ dưới 1 giây.
   - **`gemini_worker_cloud`** (Google Gemini 3.5 Flash-Lite / 3.8 Flash / 4 Argon): Sinh mã module quy mô lớn (>32K context), tái cấu trúc đa file với cửa sổ ngữ cảnh **1.000.000 tokens**, phân tích ảnh giao diện/sơ đồ (Multimodal Vision), và giải bài toán suy luận sâu với Argon.
3. **Cổng kiểm duyệt kiến trúc độc lập (DeepSeek-V4.1-Flash 1M Context)**: Triệt tiêu hoàn toàn hiện tượng "buồng vang tự kỷ" (Gemini tự sinh subagent Gemini để tự khen nhau). Soát xét RFC, SDD bundle và diff qua mô hình MoE 552B độc lập sở hữu **1.000.000 tokens context** cùng kỹ thuật nén FP4 KV cache.
4. **Trí nhớ phản xạ đa phiên (Cross-Session Memory)**: Tự động ghi nhận các giải pháp sửa lỗi thành công, đánh chỉ mục vào SQLite WAL với FTS5 BM25 và vector đặc ONNX CPU 256 chiều được fine-tune riêng (`google/embeddinggemma-2-omni` INT8 MRL), gợi ý lại giải pháp đã kiểm chứng trong **< 0.3ms**.
5. **Đồ thị cấu trúc Codebase chuẩn Graphify (Omni-Graph)**: Đồ thị quan hệ lưu trong SQLite WAL cục bộ của workspace (`.omni/codebase_graph.db`). Cung cấp **Bộ bảo vệ hợp đồng chữ ký hàm (Signature Contract Guard)**, **Cảnh báo vòng đời (Lifecycle Guard)**, **Tính bán kính ảnh hưởng Blast Radius (<2ms)**, và xuất **Đồ thị trực quan tương tác Vis.Network 9.1.6** khử hoàn toàn hiện tượng rung lắc/chuyển động vô tận.
6. **Bộ trích xuất đa ngôn ngữ toàn năng (Universal Polyglot Extractor)**: Thiết kế riêng cho "vibe coder" linh hoạt, không yêu cầu cài đặt hay biên dịch C/Rust trên Windows. Tự động nhận diện Python, JavaScript/TypeScript, Go, Rust, SQL, Shell, Markdown docs và Configs.
7. **Tự tổng hợp kỹ năng mới (Autonomous Skill Synthesis)**: Khi đối mặt với công nghệ lạ chưa có trong thư viện, Omni tự soạn thảo file `SKILL.md`, quét tĩnh AST kiểm tra an toàn, chạy kiểm thử trong sandbox và tự động thăng hạng vào thư viện cục bộ.

---

## ⚡ So sánh Tính năng Thực tế

| Tiêu chí | Nhồi Kỹ năng Tĩnh Truyền thống | Omni-Skill Orchestrator v4.2 |
|---|---|---|
| **Dung lượng Ngữ cảnh** | Nhồi 50–120 kỹ năng (**15.000–25.000 token**), gây tràn ngữ cảnh và suy giảm IQ mô hình. | **< 300 Token ở trạng thái chờ!** Giữ nguyên tắc tinh gọn; kỹ năng, quy tắc và công cụ được phân giải Đúng Lúc (JIT). |
| **Ủy thác Công nhân** | Agent tự sinh mã boilerplate và test đồ sộ, làm nghẽn ngữ cảnh chat. | **Hạm đội Tri-Worker**: Phân luồng chuyên trách cho MI50 (16GB offline), Groq (300-800 t/s LPU) và Gemini Cloud (1M context heavy coder). |
| **Kiểm soát Kiến trúc** | Subagent nội bộ dễ rơi vào "Buồng vang tự sướng" (Echo Chamber), tự khen code của nhau. | **Hội đồng Phản biện Độc lập (DeepSeek-V4.1-Flash 1M)**: Cưỡng chế kiểm duyệt với chữ ký số HMAC-SHA256, 1M context native, phản biện chéo đa hãng độc lập. |
| **Độ chính xác Định tuyến** | So khớp chuỗi con thô sơ dễ gọi nhầm sang kỹ năng không liên quan. | **Chấm điểm theo Segment + Ranh giới Từ**: Tách biệt rõ nhóm từ miền kỹ thuật (`docker`, `sqlite`, `postgres`) khỏi từ hành động chung (`fix`, `debug`, `guide`). Đạt **100% Top-1 & Top-3** trên Golden Benchmark. |
| **Trí nhớ Dài hạn** | File JSON phẳng dễ hỏng hoặc vector DB SaaS đám mây cồng kềnh. | **Trí nhớ Đa tầng Tri-Tier**: Tầng 1 non-blocking RAM spool (<0.3ms); Tầng 2 SQLite WAL nhúng FTS5 BM25 + CPU ONNX Embeddings (0MB VRAM Tax); Tầng 3 Consolidator tự động tính độ trôi dạt Ebbinghaus. |
| **Cấu trúc Codebase (Omni-Graph)** | Mơ hồ về cấu trúc hoặc dump file JSON 50MB gây sập ngữ cảnh. | **Đồ thị quan hệ SQLite WAL**: Recursive CTEs tính toán bán kính ảnh hưởng caller/callee trong <2ms. Kiểm tra vi phạm tham số gọi hàm (PEP 570, kwargs) và xuất đồ thị tĩnh Vis.Network 9.1.6 không rung lắc. |
| **Lõi Phụ thuộc** | Phụ thuộc thư viện nặng ngoài luồng, dễ lỗi môi trường. | **Lõi Python Standard Library thuần túy** cho Kernel, Hook, SQLite FTS5, và Omni-Graph (0 phụ thuộc native ngoài). |

---

## 🏗️ Kiến trúc Phân tầng

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   PRIMARY AGENT HARNESS (Free Quota)                  │
│       Google Antigravity / Claude Code / Cursor (Kiến trúc sư/Điều phối│
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Pre-Flight Reflex (<0.3ms)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   OMNI-KERNEL v4.2 ENGINE                              │
│   • L1 Reflex Hook (scripts/hook_runner.py)                           │
│   • JIT Skill & Rule Resolver (scripts/resolver.py)                    │
│   • Tri-Tier Omni-Memory (scripts/memory_engine.py - SQLite WAL FTS5)   │
│   • Omni-Graph Topology Guard (scripts/omni_graph.py - Blast Radius)   │
└──────────────────┬───────────────────────┬─────────────────────────────┘
                   │                       │
         Ủy thác triển khai code           │ Thẩm định kiến trúc
                   │                       ▼
         ┌─────────┴─────────┐   ┌──────────────────────────────────────┐
         ▼                   ▼   │       COUNCIL PROTOCOL GATE          │
┌─────────────────┐ ┌──────────┐ │   DeepSeek-V4.1-Flash (1M Context)   │
│  LOCAL WORKER   │ │   GROQ   │ │   • Chống buồng vang (Anti-Echo)     │
│ AMD MI50 (16GB) │ │ 120B LPU │ │   • Chữ ký số bảo mật HMAC-SHA256    │
│  (Sửa file đĩa) │ │  (<1s)   │ └──────────────────────────────────────┘
└─────────────────┘ └────┬─────┘
                         │ (File lớn / Ngữ cảnh 1M / Multimodal Vision)
                         ▼
                ┌──────────────────┐
                │  GEMINI WORKER   │
                │ 3.5 Lite / 3.8 / │
                │   4 Argon (1M)   │
                └──────────────────┘
```

---

## 📦 Danh mục Module Lõi

| Thành phần | Đường dẫn | Chức năng |
|---|---|---|
| **PreInvocation Hook** | `scripts/hook_runner.py` | Bộ chặn tiền khởi chạy tiêm kỹ năng JIT, quy tắc và chỉ thị hạm đội worker (<25ms). |
| **JIT Skill Resolver** | `scripts/resolver.py` | Bộ máy định tuyến kỹ năng và quy tắc theo phân đoạn (<5ms). |
| **Gemini Cloud Worker** | `scripts/gemini_worker.py` | Driver 100% Python stdlib kết nối Google Gemini 3.5/3.8/Argon (ngữ cảnh 1M, multimodal, reasoning). |
| **Gemini Worker MCP** | `D:\Antigravity\Gemini Worker\gemini_worker_mcp.py` | Server stdio JSON-RPC MCP cung cấp `gemini_heavy_code_gen`, `gemini_multimodal_vision`, và `gemini_argon_solve`. |
| **Groq Worker MCP** | `D:\Antigravity\Groq Worker\groq_worker_mcp.py` | Server stdio JSON-RPC MCP cho Groq 120B sinh code và kiểm thử dưới 1 giây. |
| **Local MI50 Worker** | `D:\Antigravity\Local Worker\local_llm_worker_mcp.py` | Sửa mã nguồn phẫu thuật tại chỗ (`fast_edit`) và thực thi ngoại tuyến trên GPU AMD MI50. |
| **Architecture Auditor** | `scripts/consult_critic.py` | Client Hội đồng Phản biện Độc lập kết nối DeepSeek-V4.1-Flash với cửa sổ 1.000.000 tokens context. |
| **Omni-Graph CLI** | `scripts/omni_graph.py` | Trình điều khiển quét mã nguồn, kiểm tra hợp đồng chữ ký và xuất đồ thị tương tác. |
| **Memory Engine** | `scripts/memory_engine.py` | Tìm kiếm lai kết hợp SQLite FTS5 BM25 và vector đặc CPU ONNX qua RRF. |
| **Autonomous Synthesizer** | `scripts/synthesizer.py` | Quy trình tự soạn thảo, kiểm tra AST, sandbox test và thăng hạng kỹ năng mới. |

---

## 🧪 Kiểm thử Tự động & Xác minh Thực nghiệm

Omni-Skill Orchestrator duy trì bộ kiểm thử tự động toàn diện với **tỷ lệ đạt 100%**:

```bash
# 1. Chạy kiểm thử đa tiến trình đồng thời trên SQLite WAL (Windows/NT)
python tests/test_concurrency_wal.py

# 2. Chạy kiểm thử phản biện sống với DeepSeek Gatekeeper (Xác thực 1M Context)
python scripts/consult_critic.py --prompt "Kiểm tra hệ thống" --mode rfc

# 3. Kiểm thử gọi trực tiếp Gemini Cloud Worker (1M Context Flash-Lite)
python scripts/gemini_worker.py --task "Test echo" --model gemini-3.5-flash-lite

# 4. Quét và trực quan hóa cấu trúc Codebase
python scripts/omni_graph.py --workspace "." --scan --visualize
```

---

## 🙏 Lời Cảm Ơn & Nguồn Cảm Hứng (Acknowledgements)

Omni-Skill Orchestrator được xây dựng dựa trên sự kế thừa và học hỏi từ các công trình mã nguồn mở xuất sắc của cộng đồng:

- **[Graphify](https://github.com/Graphify-Labs/graphify)** (*Graphify-Labs*): Người tiên phong trong việc chuyển hóa toàn bộ codebase thành đồ thị tri thức truy vấn được cho trợ lý AI, thuật toán phân bố nút xoắn ốc Fermat, và giao diện trực quan hóa tương tác Vis.Network đã trực tiếp định hình tính năng Omni-Graph.
- **[Spec Kit](https://github.com/github/spec-kit)** (*GitHub*): Dự án nguồn cảm hứng cho quy trình 10 bước Kỹ nghệ Phần mềm Theo Đặc tả (Specification-Driven Development - SDD) định hình tư duy kỷ luật kiến trúc của hệ thống.
- **[Ponytail](https://github.com/DietrichGebert/ponytail)** (*Dietrich Gebert*): Triết lý lập trình tối giản đỉnh cao (Lazy Senior Dev Mode): sự khác biệt hoàn chỉnh nhỏ nhất, ưu tiên thư viện chuẩn hơn là dependencies cồng kềnh, YAGNI, và minh bạch rủi ro.
- **[DeepSeek AI](https://github.com/deepseek-ai)** (*DeepSeek*): Mô hình MoE đột phá với kiến trúc CED và 1M context làm nền tảng cho Cổng Kiểm duyệt Kiến trúc Độc lập (Council Gate) chống buồng vang tự kỷ.
- **[Google Generative AI](https://ai.google.dev/)** (*Google DeepMind*): Cửa sổ ngữ cảnh 1.000.000 tokens, hiệu năng siêu tốc của dòng Flash và sức mạnh suy luận sâu của Argon.
- **[Groq](https://groq.com/)**: Động cơ suy luận LPU siêu tốc cho sinh mã và kiểm thử dưới 1 giây.
- **[Vis.js Network](https://github.com/visjs/vis-network)**: Engine mô phỏng vật lý và vẽ đồ thị mạng nhện tương tác mượt mà chạy trực tiếp trên trình duyệt.

---

## 📄 Bản Quyền

Giấy phép MIT. Xem chi tiết tại [LICENSE](LICENSE).
