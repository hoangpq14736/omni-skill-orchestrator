# 🧠 Omni-Skill Orchestrator v4.1: Lớp Điều Phối Kỹ Năng JIT & Bộ Nhớ Phản Xạ Cho Tác Tử AI

[![Agent Plugins 1.0.0](https://img.shields.io/badge/Spec-Agent%20Plugins%201.0.0-blue.svg)](https://agent-plugins.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)
[![Zero Dependency Kernel](https://img.shields.io/badge/Dependencies-0%20(Lõi%20Stdlib%20Thuần%20Túy)-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-277%2F277%20Passing-success.svg)]()
[![Council Gate](https://img.shields.io/badge/DeepSeek%20Council%20Gate-APPROVED-brightgreen.svg)](docs/audits/omni_kernel_v41_final_approved_verdict.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) • [Tiếng Việt](README.vi.md)

> **Lớp điều phối (harness) siêu nhẹ, vận hành cục bộ (local-first) dành cho Google Antigravity, Claude Code, Cursor và các AI coding agent.**  
> *Trang bị cơ chế định tuyến kỹ năng JIT tốc độ dưới mili-giây, kiến trúc trí nhớ đa tầng Tri-Tier (SQLite WAL + Dual-Column FTS5 BM25 + CPU ONNX Embeddings 384 chiều), tự động tổng hợp kỹ năng mới, đồ thị cấu trúc codebase chuẩn Graphify (Omni-Graph), và cổng kiểm duyệt kiến trúc độc lập — với 0 token tĩnh lãng phí.*

---

## 🎯 Omni-Skill Orchestrator thực sự là gì?

Omni **không phải** là một tác tử lập trình độc lập (như Aider, OpenCode hay OpenHands). Thay vào đó, Omni đóng vai trò là một **lớp điều phối và phản xạ tiền khởi chạy (Pre-flight Harness & Reflex Layer)** bọc ngoài mô hình chính của bạn (như Antigravity, Claude Code):

1. **Chống phình to ngữ cảnh (Context Bloat)**: Thay vì nhồi 50–120 kỹ năng và quy tắc tĩnh vào System Prompt (ngốn 15.000–25.000 token mỗi lượt chat), Omni quét hơn 500 kỹ năng trong **0.12s** và chỉ tiêm 1–3 kỹ năng/quy tắc phù hợp nhất **Đúng Lúc (Just-In-Time, < 300 token)**.
2. **Trí nhớ phản xạ đa phiên (Cross-Session Memory)**: Tự động ghi nhận các giải pháp sửa lỗi thành công, đánh chỉ mục vào SQLite WAL với FTS5 BM25 và vector đặc ONNX CPU 384 chiều (`intfloat/multilingual-e5-small`), gợi ý lại giải pháp đã kiểm chứng trong **< 0.3ms**.
3. **Đồ thị cấu trúc Codebase chuẩn Graphify (Omni-Graph)**: Đồ thị quan hệ lưu trong SQLite WAL cục bộ của workspace (`.omni/codebase_graph.db`). Cung cấp **Bộ bảo vệ hợp đồng chữ ký hàm (Signature Contract Guard)**, **Cảnh báo vòng đời (Lifecycle Guard)**, **Tính bán kính ảnh hưởng Blast Radius (<2ms)**, và xuất **Đồ thị trực quan tương tác Vis.Network 9.1.6** khử hoàn toàn hiện tượng rung lắc/chuyển động vô tận.
4. **Bộ trích xuất đa ngôn ngữ toàn năng (Universal Polyglot Extractor)**: Thiết kế riêng cho "vibe coder" linh hoạt, không yêu cầu cài đặt hay biên dịch C/Rust trên Windows. Tự động nhận diện Python, JavaScript/TypeScript, Go, Rust, SQL, Shell, Markdown docs và Configs.
5. **Tự tổng hợp kỹ năng mới (Autonomous Skill Synthesis)**: Khi đối mặt với công nghệ lạ chưa có trong thư viện, Omni tự soạn thảo file `SKILL.md`, quét tĩnh AST kiểm tra an toàn, chạy kiểm thử trong sandbox và tự động thăng hạng vào thư viện cục bộ.
6. **Cổng kiểm duyệt kiến trúc độc lập (Council Gate)**: Phát hiện các yêu cầu thiết kế hệ thống lớn (RFC, SDD, diff lớn) trong `< 25ms` logic nội bộ (`~120ms` toàn tiến trình subprocess trên Windows) mà không làm tắc nghẽn phiên chat bằng các lệnh gọi mạng đồng bộ.
7. **Động cơ Bẫy Lỗi Thực nghiệm (Episodic Anti-Patterns & Heuristic Guard)**: Tự động phát hiện và ghi nhận các lỗi thực thi dòng lệnh (exit code != 0, lỗi cú pháp quoting, thiếu module) qua bộ lọc 3 tầng, lưu vết với cơ chế TTL 14 ngày và quét dọn chủ động, ngăn chặn tác tử rơi lại vào các bẫy lỗi cũ mà không cần viết prompt thủ công.
8. **Trình Quản lý Dịch vụ Chạy Nền Windows (Windows Service & Task Scheduler Manager)**: Quản lý tác vụ chạy ngầm định kỳ 15 phút qua `pythonw.exe` và Task Scheduler (`scripts/service_manager.py`), tự động dọn rác, suy giảm Ebbinghaus và quét bản ghi hết hạn mà không hiện cửa sổ terminal hay khóa tiến trình.
9. **Tính Di Động Toàn Năng & Định Danh Git-Root (Universal Portability)**: Tách rời hoàn toàn khỏi các đường dẫn ổ đĩa cố định và tên tài khoản máy tính. Sử dụng mã băm URL Git Remote để nhận diện dự án liên ổ đĩa (Dual-Lookup), cung cấp bộ cài đặt 1-click (`setup.bat` / `scripts/bootstrap.py`), và tự động chuyển vùng sang Groq Cloud LPU khi worker cục bộ offline.

---

## 🚀 Khởi Tạo 1-Click Khi Đổi Máy (setup.bat)

Khi chuyển sang máy tính mới hoặc cài lại Windows, bạn chỉ cần nhấp đúp vào `setup.bat` (hoặc gõ `./setup.bat` trong terminal). Tệp sẽ tự động:
- Phát hiện môi trường Python (hoặc hiển thị thông báo tự động cài đặt qua `winget` nếu máy chưa có).
- Đồng bộ mã nguồn plugin vào thư mục người dùng (`%USERPROFILE%/.gemini/...`).
- Xác thực schema SQLite WAL, đăng ký lịch chạy ngầm Task Scheduler 15 phút, và quét cây tô-pô Omni-Graph dưới 2 giây.

---

## ⚡ So sánh Tính năng Thực tế

| Tiêu chí | Nhồi Kỹ năng Tĩnh Truyền thống | Omni-Skill Orchestrator v4.1 |
|---|---|---|
| **Dung lượng Ngữ cảnh** | Nhồi 50–120 kỹ năng (**15.000–25.000 token**), gây tràn ngữ cảnh và suy giảm IQ mô hình. | **< 300 Token ở trạng thái chờ!** Giữ nguyên tắc tinh gọn; kỹ năng, quy tắc và công cụ được phân giải Đúng Lúc (JIT). |
| **Độ chính xác Định tuyến** | So khớp chuỗi con thô sơ dễ gọi nhầm sang kỹ năng không liên quan. | **Chấm điểm theo Segment + Ranh giới Từ**: Tách biệt rõ nhóm từ miền kỹ thuật (`docker`, `sqlite`, `postgres`) khỏi từ hành động chung (`fix`, `debug`, `guide`). Đạt **100% Top-1 & Top-3** trên bộ Golden Benchmark 25 câu hỏi. |
| **Trí nhớ Dài hạn** | File JSON phẳng dễ hỏng hoặc vector DB SaaS đám mây cồng kềnh. | **Trí nhớ Đa tầng Tri-Tier**: Tầng 1 non-blocking RAM spool (<0.3ms); Tầng 2 SQLite WAL nhúng FTS5 BM25 + CPU ONNX Embeddings (0MB VRAM Tax); Tầng 3 Consolidator tự động tính độ trôi dạt Ebbinghaus. |
| **Cấu trúc Codebase (Omni-Graph)** | Mù mờ về cấu trúc hoặc dump file JSON 50MB gây sập ngữ cảnh. | **Đồ thị quan hệ SQLite WAL**: Recursive CTEs tính toán bán kính ảnh hưởng caller/callee trong <2ms. Kiểm tra vi phạm tham số gọi hàm (PEP 570, kwargs) và xuất đồ thị tĩnh Vis.Network 9.1.6 không rung lắc. |
| **Trích xuất Đa ngôn ngữ** | Bị giới hạn 1 ngôn ngữ hoặc phụ thuộc công cụ biên dịch C cồng kềnh. | **Universal Polyglot Extractor (Zero-Dependency)**: Native stdlib AST cho Python + regex streaming cho JS/TS, Go, Rust, SQL, Shell và Markdown docs. |
| **Tổng hợp Kỹ năng** | Lập trình viên phải tự gõ thủ công từng file cấu hình cho mỗi thư viện mới. | **Quy trình Tự động**: `scripts/synthesizer.py` tự tạo mẫu, kiểm tra cú pháp AST, kiểm chứng assert trong sandbox và tự tái lập chỉ mục trong <150ms. |
| **Kiểm soát Kiến trúc** | Subagent nội bộ dễ rơi vào "Buồng vang tự sướng" (Echo Chamber), tự khen code của nhau. | **Hội đồng Phản biện Độc lập (DeepSeek-V4.1-Flash)**: Cưỡng chế kiểm duyệt với chữ ký số HMAC-SHA256 và mã băm SHA-256 của file đích mà không làm nghẽn luồng hook. |
| **Lõi Phụ thuộc** | Phụ thuộc thư viện nặng ngoài luồng, dễ lỗi môi trường. | **Lõi Python Standard Library thuần túy** cho Kernel, Hook, SQLite FTS5 và Omni-Graph (0 phụ thuộc native ngoài). |

---

## 🌐 Kiến trúc Omni-Graph (Đồ thị Codebase Chuẩn Graphify)

Omni-Graph thực thi nguyên tắc **Zero-Conflict Duality**:
- **Trí nhớ Nhận thức Toàn cục (Global Cognitive Memory)**: Lưu trong `omni_memory.db` để học hỏi liên phiên và tích lũy tri thức xuyên dự án.
- **Tô-pô Codebase Cục bộ (Local Codebase Topology)**: Lưu trong `<workspace>/.omni/codebase_graph.db` (chế độ SQLite WAL), hoàn toàn độc lập cho từng dự án.

### Các thành phần cốt lõi:
1. **Lưu trữ Đồ thị Quan hệ (`scripts/omni_graph/storage.py`)**:
   - Các bảng chuẩn hóa: `nodes`, `signatures`, `edges`, `lifecycle_hooks`, và `codebase_files_meta`.
   - 7 chỉ mục B-Tree bao phủ giúp truy vấn đường dẫn gọi hàm trong nháy mắt.
2. **Bộ phát hiện thay đổi 2 tầng (`scripts/omni_graph/fingerprint.py`)**:
   - Tầng 1: So sánh `mtime` và `size_bytes` trong **< 2ms** cho hàng trăm file.
   - Tầng 2: Kiểm tra băm SHA-256 khi tem thời gian thay đổi.
3. **Bộ bảo vệ hợp đồng chữ ký hàm (`scripts/omni_graph/validator.py`)**:
   - Chuẩn hóa receiver method (tự động loại trừ `self` và `cls`).
   - Kiểm soát nghiêm ngặt tham số positional-only (PEP 570), keyword-only, và tham số lạ không tồn tại.
   - Ngăn chặn lỗi gãy giao diện trước khi mã nguồn được chạy.
4. **Trình trực quan hóa Vis-Network (`scripts/omni_graph/visualizer.py`)**:
   - Nhúng Vis.Network 9.1.6 với bảng màu Tableau 10 của Graphify.
   - Phân bổ vị trí hạt giống theo xoắn ốc Fermat ($x = 35 \sqrt{i} \cos(2.4 i)$, $y = 35 \sqrt{i} \sin(2.4 i)$).
   - Tự động đóng băng động lực học ở bước 200 (**khử hoàn toàn hiện tượng rung lắc/di chuyển liên tục**).
   - Thanh điều khiển Sidebar với chuyển đổi Theme (Dark/Light/System), tìm kiếm autocomplete, bảng tra cứu node và bộ lọc cụm cộng đồng.

---

## 🛠️ Danh mục Module Lõi

| Thành phần | Đường dẫn | Chức năng |
|---|---|---|
| **PreInvocation Hook** | `scripts/hook_runner.py` | Bộ chặn tiền khởi chạy tiêm kỹ năng JIT, quy tắc và chỉ thị bộ nhớ (<25ms). |
| **JIT Skill Resolver** | `scripts/resolver.py` | Bộ máy định tuyến kỹ năng và quy tắc theo phân đoạn (<5ms). |
| **Omni-Graph CLI** | `scripts/omni_graph.py` | Trình điều khiển quét mã nguồn, kiểm tra hợp đồng chữ ký và xuất đồ thị. |
| **Omni-Graph Engine** | `scripts/omni_graph/` | Trọn bộ động cơ đồ thị: `storage.py`, `fingerprint.py`, `visitor.py`, `validator.py`, `traversal.py`, `visualizer.py`. |
| **Autonomous Synthesizer** | `scripts/synthesizer.py` | Quy trình tự soạn thảo, kiểm tra AST, sandbox test và thăng hạng kỹ năng mới. |
| **Skill Indexer** | `scripts/indexer.py` | Bộ đánh chỉ mục siêu tốc quét 500+ kỹ năng trong 0.12s. |
| **Experiential Memory** | `scripts/experiential_memory.py` | Lưu trữ và truy xuất các trace thực thi đã kiểm chứng dưới 1ms. |
| **Memory Engine** | `scripts/memory_engine.py` | Tìm kiếm lai kết hợp SQLite FTS5 BM25 và vector dense qua RRF. |
| **Embedding Service** | `scripts/embedding_service.py` | Tạo vector nhúng cục bộ trên CPU bằng `fastembed`. |
| **Memory Consolidator** | `scripts/consolidator.py` | Tiến trình chạy nền gom dữ liệu staging, thăng hạng tri thức và áp dụng suy giảm Ebbinghaus. |
| **Architecture Auditor** | `scripts/consult_critic.py` | Client phản biện độc lập kết nối DeepSeek-V4.1-Flash để review kiến trúc. |
| **Anti-Pattern Guard** | `scripts/antipattern_guard.py` | Bộ đánh chặn lỗi hậu thực thi 3 tầng phân loại & chống bẫy tái diễn. |
| **Windows Service Manager** | `scripts/service_manager.py` | Bộ quản lý Windows Task Scheduler chạy nền silent consolidator qua `pythonw.exe`. |
| **Environment Bootstrapper** | `scripts/bootstrap.py` | Trình cài đặt môi trường 1-Click, tự động liên kết plugin, khởi tạo SQLite WAL, Task Scheduler và Omni-Graph. |

---

## 🧪 Kiểm thử Tự động & Xác minh Thực nghiệm

Omni-Skill Orchestrator duy trì bộ kiểm thử tự động toàn diện với **tỷ lệ đạt 100%**:

```bash
# 1. Chạy toàn bộ kiểm thử lõi và cổng kiểm duyệt DeepSeek (45 tests PASS)
python -m pytest specs/002-deepseek-v41-auditor/tests/

# 2. Chạy bài thách thức thực nghiệm & validator hợp đồng chữ ký (16/16 PASS)
python tests/test_omni_graph_validator_empirical.py

# 3. Chạy kiểm thử tích hợp không gian làm việc thực tế (2/2 PASS)
python tests/test_omni_graph_live.py

# 4. Quét và trực quan hóa bất kỳ workspace nào
python scripts/omni_graph.py --workspace "." --scan --visualize

# 5. Chạy bộ kiểm thử Bẫy Lỗi Thực nghiệm & Bộ lọc Đánh chặn (7/7 PASS)
python -m unittest tests/test_antipatterns.py tests/test_antipattern_guard.py tests/test_consolidator_antipatterns.py

# 6. Chạy bộ kiểm thử Di Động & Khử Hardcode PII (6/6 PASS)
python -m unittest tests/test_portability.py
```

---

## 🙏 Lời Cảm Ơn & Nguồn Cảm Hứng (Acknowledgements)

Omni-Skill Orchestrator được xây dựng dựa trên sự kế thừa và học hỏi từ các công trình mã nguồn mở xuất sắc của cộng đồng. Chúng tôi xin gửi lời cảm ơn và tri ân sâu sắc tới các tác giả và dự án tiên phong sau:

- **[Graphify](https://github.com/Graphify-Labs/graphify)** (*Graphify-Labs*): Người tiên phong trong việc chuyển hóa toàn bộ codebase thành đồ thị tri thức truy vấn được cho trợ lý AI, thuật toán phân bổ nút xoắn ốc Fermat, và giao diện trực quan hóa tương tác Vis.Network đã trực tiếp định hình nên tính năng Omni-Graph.
- **[Spec Kit](https://github.com/github/spec-kit)** (*GitHub*): Dự án nguồn cảm hứng cho quy trình 10 bước Kỹ nghệ Phần mềm Theo Đặc tả (Specification-Driven Development - SDD) định hình tư duy kỷ luật kiến trúc của hệ thống.
- **[Ponytail](https://github.com/DietrichGebert/ponytail)** (*Dietrich Gebert*): Triết lý lập trình tối giản đỉnh cao (Lazy Senior Dev Mode): sự khác biệt hoàn chỉnh nhỏ nhất, ưu tiên thư viện chuẩn hơn là dependencies cồng kềnh, YAGNI, và minh bạch rủi ro.
- **[Hermes-Agent](https://github.com/NousResearch/hermes-agent)** (*Nous Research*): Cấu trúc tác tử tự chủ cao (high-agency), mô hình điều phối đa công cụ và cơ chế phản xạ bộ nhớ thực nghiệm.
- **[Awesome Agent Skills](https://github.com/VoltAgent/awesome-agent-skills)** (*VoltAgent*): Hệ thống phân loại và kho kỹ năng quy chuẩn mẫu mực cho các tác tử AI.
- **[DeepSeek AI](https://github.com/deepseek-ai)** (*DeepSeek*): Mô hình lý luận đột phá làm nền tảng cho Cổng Kiểm duyệt Kiến trúc Độc lập (Council Gate) chống buồng vang tự kỷ.
- **[Vis.js Network](https://github.com/visjs/vis-network)**: Engine mô phỏng vật lý và vẽ đồ thị mạng nhện tương tác mượt mà chạy trực tiếp trên trình duyệt.
- **[FastEmbed](https://github.com/qdrant/fastembed)** (*Qdrant*) & **[IntFloat](https://huggingface.co/intfloat)**: Mô hình nhúng CPU ONNX hiệu năng cao (`multilingual-e5-small`) cho phép truy xuất bộ nhớ ngữ nghĩa với 0MB tiêu tốn GPU.

---

## 📄 Bản quyền

Giấy phép MIT. Xem chi tiết tại [LICENSE](LICENSE).
