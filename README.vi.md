# 🧠 Omni-Kernel v3.0: Hệ điều hành Nhận thức Tự trị Toàn năng

[![Agent Plugins 1.0.0](https://img.shields.io/badge/Spec-Agent%20Plugins%201.0.0-blue.svg)](https://agent-plugins.org)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://python.org)
[![Zero Dependency](https://img.shields.io/badge/Dependencies-0%20(Pure%20Stdlib)-brightgreen.svg)]()
[![Tests](https://img.shields.io/badge/Tests-28%2F28%20Passing-success.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[English](README.md) • [Tiếng Việt](README.vi.md)

> **Hệ điều hành Nhận thức AI Tự trị Toàn năng dành cho Google Antigravity, Claude Code, Cursor và các Framework Tác tử AI.**  
> *Tích hợp Điều phối Nhận thức 2 Tầng (L1 Reflex vs. L2 Strategist Subagent), Tự động hóa qua Lifecycle Hook PreInvocation, Ảo hóa Không phá hủy Mọi Workspace (Đồng hóa Cursor/Claude/Gemini rules), Kỹ năng JIT, Quy tắc Tự suy diễn, Điều phối MCP Động và Tự sinh Kỹ năng Mới với 0 static token lãng phí.*

---

## ⚡ Tại sao cần Omni-Kernel?

Các hệ thống tác tử AI truyền thống thường đối mặt với vấn đề phình to ngữ cảnh (Context Bloat), luật lệ cứng nhắc, hao tổn hạn ngạch token nhanh chóng và thiếu khả năng thích ứng trước các công nghệ lạ.

| Tiêu chí | Hệ thống Kỹ năng Tĩnh Truyền thống | Omni-Kernel v3.0 |
|---|---|---|
| **Dung lượng Ngữ cảnh (Tokens)** | Nhồi 50–120 kỹ năng & quy tắc tĩnh vào System Prompt (**15.000–25.000 tokens**), gây tràn ngữ cảnh và suy giảm IQ của mô hình. | **< 300 Tokens ở trạng thái chờ!** Giữ nguyên tắc Ring 0 tinh gọn; kỹ năng, quy tắc miền và công cụ được phân giải Đúng Lúc (JIT). |
| **Điều phối Nhận thức (Routing)** | Luồng thực thi đơn khối. Đốt token của mô hình cao cấp cho các câu lệnh đơn giản. | **Điều phối 2 Tầng (Dual-Tier Routing)**: Tầng L1 Fast Reflex (0-token, <1ms) xử lý 85% tác vụ; Tầng L2 Subagent chỉ kích hoạt khi gặp kiến trúc hoặc debug phức tạp. |
| **Bảo mật & Quy tắc miền** | Không ổn định: Chỉ kích hoạt bảo mật nếu người dùng gõ từ khóa "bảo mật" hoặc "security". | **Đồ thị Tự suy diễn (Entailment Graph)**: Tự động khóa các quy tắc bảo mật bắt buộc theo miền công nghệ (Web $\rightarrow$ XSS/CORS; DB $\rightarrow$ Parameterized SQL; Docker $\rightarrow$ Non-root user). |
| **Khả năng Tương thích Dự án** | Phải cấu hình lại thủ công cho từng repository và từng IDE khác nhau. | **Bộ Ảo hóa Dự án (Workspace Assimilator)**: Quét không phá hủy và đồng hóa `.cursorrules`, `GEMINI.md`, `CLAUDE.md`, và kỹ năng nội bộ trong <1ms mà không sửa đổi file gốc. |
| **Khả năng Thích ứng & Tự học** | Kỹ năng tĩnh cố định. Bất lực trước công nghệ hoặc vi điều khiển lạ. | **Trình Tổng hợp Kỹ năng Tự trị (Synthesizer)**: Tự thiết kế kỹ năng, kiểm thử trong môi trường hộp cát (Sandbox Subprocess) và tự thăng hạng vào thư viện. |
| **Tốc độ & Phụ thuộc** | Phụ thuộc cơ sở dữ liệu vector nặng nề, API embedding hoặc thư viện cồng kềnh. | **0 Phụ thuộc ngoài (100% Python Standard Library)**. Lập chỉ mục 500+ kỹ năng trong **0.10s**, phân giải trong **~1ms** với tốc độ **1.000+ QPS**. |

---

## 🏗️ Kiến trúc Hệ thống

Omni-Kernel vận hành như một **Tầng trung gian Nhận thức (Cognitive Middleware)** xác định và có tốc độ sub-millisecond bên dưới mô hình AI:

```text
                      ┌────────────────────────────────────┐
                      │    USER PROMPT & REPO WORKSPACE   │
                      └─────────────────┬──────────────────┘
                                        │
                         Phát hiện Tự trị Kênh Kép (Dual-Channel)
                                        │
              ┌──────────────────────────┴───────────────────────────┐
              ▼                                                       ▼
     [KÊNH 1: TĨNH]                                         [KÊNH 2: ĐỘNG]
     Dấu hiệu Stack Workspace                               Ý định Ngữ nghĩa & Từ đồng nghĩa
     (package.json, Cargo.toml,                             (Bộ ánh xạ song ngữ Anh - Việt,
      requirements.txt, v.v.)                                Từ khóa task, Dấu vết lỗi)
              │                                                       │
              └──────────────────────────┬───────────────────────────┘
                                         ▼
                      ┌────────────────────────────────────┐
                      │    ĐỒ THỊ TỰ SUY DIỄN NHẬN THỨC    │
                      │  - Quy tắc Miền Tự suy ra (Ring 3) │
                      │  - Đề xuất Công cụ MCP Ngoại vi    │
                      │  - Ma trận Phân xử 4 Tầng          │
                      │  - Điểm số Phức tạp (0-100)        │
                      └─────────────────┬──────────────────┘
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼ (Điểm < 50)                                   ▼ (Điểm >= 50)
      ┌────────────────────────┐                     ┌────────────────────────┐
      │ TẦNG 1: L1 FAST REFLEX │                     │ TẦNG 2: L2 STRATEGIST  │
      │ ⚡ Khóa Quota Guard     │                     │ 🧠 Phê duyệt Subagent  │
      │ 0 Extra Token, <50ms   │                     │ 'omni-strategist' live │
      │ Pre-Flight Tạm thời    │                     │ Lập Kế hoạch Chuyên sâu│
      └────────────────────────┘                     └────────────────────────┘
```

---

## 🚀 Thước đo Hiệu năng (Benchmarks)

Được đo lường trên máy trạm tiêu chuẩn của lập trình viên:

* **Lập chỉ mục Đảo (Inverted Indexing):** 501+ kỹ năng từ 4 nguồn được chỉ mục hóa trong **0.10s** (`indexer.py`).
* **Kiểm tra Độ mới của Cache:** Phát hiện thay đổi file qua `mtime` hệ thống trong **0.42ms** (`is_registry_stale()`).
* **Phân giải Ý định & Stack:** Truy vấn song ngữ Anh - Việt đến kỹ năng tối ưu trong **0.92ms** (`resolver.py`).
* **Độ trễ Lifecycle Hook:** Khởi động tiến trình, đọc stdin, phân giải và xuất kết quả ra stdout trong **< 45ms** (`hook_runner.py`).
* **Thông lượng (Throughput):** **1.078 Truy vấn / Giây** trên luồng đơn CPU.
* **Độ chính xác:** **85.0%** Top-1 Accuracy, **95.0%** Top-3 Accuracy, **100%** Khớp Quy tắc Bảo mật trên 20 lĩnh vực kỹ thuật khác nhau.

---

## 📦 Cài đặt

### Cách 1: Plugin Google Antigravity (Khuyến nghị)

1. Clone repository này vào thư mục plugin của bạn:
   ```bash
   git clone https://github.com/hoangpq14736/omni-skill-orchestrator.git ~/.gemini/config/plugins/omni-skill-orchestrator
   ```
2. Kích hoạt plugin qua Antigravity CLI hoặc giao diện:
   ```bash
   agy plugin enable omni-skill-orchestrator
   ```
3. *Không cần cấu hình thêm.* Hook `PreInvocation` toàn cục sẽ tự động chạy ngầm trước mỗi câu lệnh.

### Cách 2: Chạy CLI Độc lập & Tích hợp Tùy biến

Omni-Kernel hoạt động ở bất kỳ môi trường nào có cài Python 3.10+:

```bash
# Phân giải kỹ năng tối ưu cho một yêu cầu
python scripts/resolver.py --intent "tối ưu truy vấn postgresql và tạo migration"

# Phân giải kèm nhận diện công nghệ của thư mục dự án
python scripts/resolver.py --workspace "./my-rust-project" --intent "viết integration test"

# Xem chi tiết lượt kích hoạt gần nhất (Bảng điều khiển Telemetry)
python scripts/resolver.py --last

# Dạy AI học từ phản hồi (Tự tiến hóa / Meta-Evolution)
python scripts/resolver.py --intent "canvas game" --workspace "./my-game" --feedback generative_ui

# Tự động tạo và kiểm thử kỹ năng mới trong sandbox
python scripts/synthesizer.py --name "modbus-rtu-reader" --desc "Serial protocol reader for industrial sensors" --test "assert True"

# Xem thống kê tự học
python scripts/resolver.py --learn-stats
```

---

## 🛠️ Danh mục Module

| Thành phần | Đường dẫn | Mô tả chức năng |
|---|---|---|
| **PreInvocation Hook** | `scripts/hook_runner.py` | Bắt sự kiện trước lượt chat trong <45ms. Tiêm chỉ dẫn Pre-Flight tạm thời (`ephemeralMessage`) không làm phình lịch sử chat. |
| **Dual-Tier Router** | `scripts/dual_tier.py` | Tính điểm độ phức tạp (0-100). Khóa Quota Guard cho task đơn giản (L1) và chỉ kích hoạt Subagent L2 khi cần thiết. |
| **Experiential Memory** | `scripts/experiential_memory.py` | Bộ nhớ thực nghiệm đa phiên truy hồi giải pháp code và lệnh CLI đã kiểm chứng trong <0.3ms không cần suy luận lại. |
| **Progress & Growth Reporter** | `scripts/reporter.py` | Tạo báo cáo tiến trình Markdown & JSON chi tiết các chỉ số KPI, tokens tiết kiệm, top skills và tri thức tích lũy. |
| **Omni-MCP Virtual Bus** | `scripts/mcp_gateway.py` | Cổng phân luồng & định tuyến MCP JIT. Lập chỉ mục 80+ công cụ qua 25 máy chủ MCP trong <25ms, định tuyến trong <0.3ms và kiểm định tham số. |
| **Workspace Assimilator** | `scripts/assimilator.py` | Đồng hóa không phá hủy các quy tắc `.cursorrules`, `GEMINI.md`, `CLAUDE.md`, và skills nội bộ của bất kỳ repo nào với ưu tiên cao nhất (`SCOPE_PRIORITY = 40`). |
| **Unified Resolver** | `scripts/resolver.py` | Lõi phân xử tốc độ sub-millisecond cho Kỹ năng, Quy tắc Miền, Công cụ MCP và Đánh giá Nhận thức. |
| **Skill Synthesizer** | `scripts/synthesizer.py` | Quy trình tự động phác thảo kỹ năng, chạy thử nghiệm sandbox và thăng hạng vào thư viện. |
| **Inverted Indexer** | `scripts/indexer.py` | Bộ phân tích YAML frontmatter tốc độ cao và tạo chỉ mục đảo trong 0.1s. |
| **Subagent Definition** | `agents/omni-strategist.json` | Cấu hình subagent chuyên trách cho việc lập kế hoạch kiến trúc và gỡ lỗi tận gốc. |

---

## 🧪 Kiểm thử Tự động

Omni-Kernel duy trì bộ kiểm thử tự động với **tỷ lệ đạt 100% (28/28 tests)**:

```bash
python tests/test_engine.py
```

```text
............................
----------------------------------------------------------------------
Ran 28 tests in 2.02s

OK
```

Chạy bộ kiểm thử benchmark tải và bảo mật:
```bash
python tests/benchmark_suite.py
```

---

## 🤝 Triết lý Kỹ thuật: Xây dựng trên nền tảng Ponytail

Omni-Kernel tuân thủ nghiêm ngặt **Triết lý Kỹ sư Ponytail (Tối giản & Đáng tin cậy)**:
* **Dòng code tốt nhất là dòng code không cần phải viết.** Giải pháp làm việc nhỏ gọn nhất luôn chiến thắng.
* Zero external dependencies (100% Python Standard Library: `os`, `json`, `re`, `time`, `urllib`).
* Bất biến là ưu tiên, báo lỗi rõ ràng kèm ngữ cảnh, tuyệt đối không âm thầm nuốt ngoại lệ.
* Bơm ngữ cảnh tạm thời (JIT Ephemeral) thay vì nhồi nhét quy tắc tĩnh gây ô nhiễm bộ nhớ.

---

## 📄 Giấy phép

Phát hành theo giấy phép MIT License. Xem chi tiết tại [LICENSE](LICENSE).
