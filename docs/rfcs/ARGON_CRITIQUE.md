Bản thiết kế Omni-Memory v4.0 nghe rất kêu trên slide thuyết trình, nhưng dưới góc nhìn của một Principal Systems Architect, bạn đang lấy các con số micro-benchmark trong điều kiện phòng thí nghiệm để che đậy những điểm nghẽn chí mạng ở cấp độ hệ điều hành, I/O và toán học.

Dưới đây là bản mổ xẻ toàn diện từng tầng trong kiến trúc của bạn — bắt đầu từ chính thứ bạn đang tự tin nhất.

0. Đập tan sự tự tin: Ảo tưởng về ngân sách 0.15ms (L1) và 1.5ms (L2)

Trước khi đi vào 3 điểm bạn yêu cầu, hãy nhìn thẳng vào hai con số "đáng tự hào" của bạn:

Ngụy biện Micro-benchmark ở L1 (0.0035ms Jaccard / 0.15ms tổng):
Bạn đo 0.0035ms bằng cách bấm giờ hàm tính tập hợp trong RAM, nhưng hook_runner.py được kích hoạt như thế nào? Nếu pre-flight hook được gọi như một tiến trình con (subprocess CLI) trước mỗi turn, riêng thời gian khởi tạo Python interpreter + nạp thư viện trên Windows đã ngốn 15ms đến 40ms — vượt ngân sách 0.3ms gấp 100 lần. Ngay cả khi bạn giữ nó sống dưới dạng daemon, việc "phi đồng bộ hóa ghi đĩa ra background thread" trong Python vẫn bị trói bởi GIL (Global Interpreter Lock). Và nguy hiểm hơn: nếu tiến trình chính bị ngắt hoặc crash trước khi daemon thread kịp flush xuống đĩa, toàn bộ log trong hàng đợi RAM sẽ bốc hơi (Silent Data Loss).

Sự bất khả thi vật lý của ngân sách 1.5ms ở L2:
Để thực hiện Dense Vector Search ở L2, bạn phải biến câu truy vấn (query) ở turn hiện tại thành một vector float32, sau đó mới tính Cosine Similarity. Bản thân việc gọi qua loopback HTTP 127.0.0.1:8080 tới worker MI50 (TCP handshake/keep-alive + JSON serialization + tokenization + forward pass của model) đã tốn tối thiểu 8ms đến 25ms. Con số "dưới 1.5ms" của bạn thực chất đã ăn gian bằng cách bỏ qua thời gian sinh query embedding.

Cái giá của "SQLite thuần không cần Vector DB":
Lưu BLOB float32 trong SQLite và tính Cosine Similarity trên RAM nghĩa là gì? Ở mức 500 bản ghi, bạn SELECT toàn bộ BLOB lên RAM và nhân ma trận bằng NumPy trong 1ms. Nhưng mục tiêu của bạn là Lifelong Partner (hàng chục ngàn đến hàng trăm ngàn ký ức). Với 50.000 vectors (giả sử 1024 chiều = 4KB/vector), mỗi turn bạn định đọc và giải tuần tự hóa (deserialize) 200MB BLOB qua giao tiếp C-Python của SQLite trong 1.5ms? Nếu bạn giữ sẵn ma trận NumPy trên RAM để tránh đọc SQLite, thì mỗi khi có đa phiên (multi-session) ghi thêm vector mới, bạn đồng bộ (cache invalidation) các ma trận RAM giữa các tiến trình kiểu gì mà không làm nổ tung bộ nhớ?

1. Concurrency & Lock Contention trên SQLite WAL + Cái bẫy FTS5

Bật PRAGMA journal_mode=WAL; không biến SQLite thành PostgreSQL. WAL chỉ cho phép nhiều luồng đọc cùng lúc với MỘT luồng ghi duy nhất. Mọi luồng ghi thứ hai đều bị chặn cứng bởi khóa cấp file (SQLITE_BUSY).

Đụng độ Đa Phiên & Tiến trình L3 (Write Lock Starvation)

Hãy hình dung kịch bản thực tế trên máy của bạn:

L1 Background Thread liên tục xả (flush) activation logs xuống SQLite sau mỗi turn.

Nhiều phiên Agent (Multi-session / Sub-agents) cùng lúc ghi episodic memory mới vào L2.

L3 Consolidation ("Giấc ngủ AI") thức dậy, quét bảng, cập nhật lại hàng loạt điểm 
𝑆
(
𝑡
)
S(t), và chạy lệnh DELETE thanh lọc các bản ghi có 
𝑆
(
𝑡
)
<
0.20
S(t)<0.20.

Khi bạn INSERT, UPDATE, hoặc DELETE trên một bảng có gắn FTS5, SQLite không chỉ sửa một dòng dữ liệu — nó phải tháo dỡ và ghi lại các B-Tree của chỉ mục đảo (inverted index) và kích hoạt quá trình gộp phân đoạn (FTS5 segment merge). Một giao dịch batch của L3 sẽ chiếm giữ khóa RESERVED/PENDING đủ lâu để làm toàn bộ các background thread của L1 dính lỗi SQLITE_BUSY: database is locked. Nếu L1 retry theo kiểu exponential backoff, hàng đợi ghi trên RAM sẽ phình to; nếu không retry đúng cách, bạn mất dữ liệu.

Hiện tượng Phình file WAL (WAL Checkpoint Starvation)

Trong chế độ WAL, dữ liệu ghi mới nằm ở file .db-wal và chỉ được gộp (checkpoint) về file .db chính khi không còn bất kỳ giao dịch đọc (read transaction) nào tham chiếu đến các trang cũ. Với kiến trúc đa phiên giữ kết nối mở hoặc quên đóng cursor ngay lập tức trong Python sqlite3, quá trình auto-checkpoint sẽ bị đói (starved). File .db-wal sẽ phình lên hàng trăm MB, biến các truy vấn đọc từ chỗ 
𝑂
(
1
)
O(1) thành cuộc rà soát chậm chạp qua WAL-index.

Lỗ hổng chết người của unicode61 remove_diacritics 2 trong Tiếng Việt

Bạn tự hào rằng remove_diacritics 2 xử lý triệt để song ngữ Anh/Việt có dấu và không dấu. Thực tế: nó phá nát độ chính xác (Precision) của BM25 đối với tiếng Việt.

Tiếng Việt là ngôn ngữ đơn lập, thanh điệu quyết định nghĩa. Khi cạo sạch dấu bằng remove_diacritics 2, các từ hoàn toàn không liên quan như "ma", "má", "mà", "mả", "mã", "mạ", hay "cơ", "cờ", "cỡ", "có", "cọ" đều bị gộp chung thành một token duy nhất (ma, co).

Hệ quả: Tần suất xuất hiện từ (Term Frequency) bị bóp méo, còn điểm nghịch đảo tần suất tài liệu (IDF) của các từ có dấu đặc thù bị sụp đổ vì bị đánh đồng với các từ phổ thông không dấu. Tập ứng viên từ FTS5 đưa vào công thức RRF (
𝑘
=
60
k=60) sẽ ngập tràn nhiễu (False Positives).

2. Quả bom nổ chậm 16GB VRAM trên MI50 & Ác mộng WDDM TDR

Chạy AMD Instinct MI50 (kiến trúc Vega 20, 16GB HBM2) trên môi trường Windows qua tầng điều khiển WDDM là đi trên dây. Khác với chế độ TCC (Compute-only) trên Linux ROCm, WDDM đặt GPU dưới sự kiểm soát của trình lập lịch đồ họa Windows: bất kỳ kernel tính toán nào chiếm GPU quá thời gian quy định (mặc định 2 giây nếu chưa can thiệp sâu hoặc khi vượt ngưỡng TdrDelay) mà không trả quyền phản hồi về cho OS sẽ bị Windows coi là treo cứng và kích hoạt TDR (Timeout Detection and Recovery) — reset toàn bộ driver.

Nghịch lý Port 8080: Xếp hàng (Head-of-Line Blocking) hay Nổ VRAM?

Bạn thiết kế "Vector embeddings sinh từ local worker MI50 (port 8080)". Ở đây chỉ có 2 trường hợp xảy ra, và cả 2 đều dẫn đến thảm họa:

Trường hợp A: Dùng chung một tiến trình server trên port 8080 cho cả LLM và Embedding.
Nếu một phiên đang nhờ MI50 suy luận (inference) một đoạn code dài mất 10 giây, toàn bộ Compute Units của Vega 20 đang bận. Ngay lúc đó, một phiên khác (hoặc chính luồng pre-flight của turn tiếp theo) gọi vào port 8080 để xin vector embedding cho L2. Request embedding đó sẽ bị chặn cứng trong hàng đợi HTTP (Head-of-Line Blocking) suốt 10 giây chờ LLM nhả slot. Ngân sách 1.5ms của L2 biến thành 10.000ms.

Trường hợp B: Chạy song song 2 model (LLM + Embedding) trên cùng 16GB HBM2.
Một model LLM tầm trung (ví dụ 14B Q4_K_M) cộng với KV Cache (context 8k–16k) đã ngốn từ 11GB đến 14GB VRAM. Cơ chế "fallback sang ONNX/CPU nếu VRAM chạm ngưỡng 12GB" của bạn mắc lỗi kinh điển TOCTOU (Time-of-Check to Time-of-Use):

Tại mili-giây thứ 0: Hook kiểm tra thấy VRAM đang ở mức 11.8GB (nhỏ hơn 12GB) → Quyết định đẩy việc tính Embedding vào MI50.

Tại mili-giây thứ 5: Trong lúc kernel Embedding đang chạy dở trên GPU, tiến trình LLM cấp phát thêm KV Cache hoặc scratchpad buffer cho một prompt lớn, đẩy tổng nhu cầu bộ nhớ vọt qua ngưỡng vật lý 16GB.

Cái chết mang tên WDDM Paging: Khi thiếu VRAM, WDDM không báo lỗi Out-Of-Memory ngay mà âm thầm đẩy (page out) các trang bộ nhớ từ HBM2 qua khe PCIe xuống System RAM. Băng thông HBM2 là hàng trăm GB/s, trong khi PCIe bị thắt cổ chai. Kernel của Vega 20 bị khựng lại chờ dữ liệu từ System RAM, thời gian thực thi kéo dài vượt ngưỡng TdrDelay, và BÙM — Windows reset driver GPU, giết chết cả tiến trình LLM lẫn tiến trình Embedding.

Sự đứt gãy không gian Vector (Manifold Mismatch) khi Fallback

Giả sử cơ chế fallback sang ONNX/CPU của bạn hoạt động. Khi VRAM dưới 12GB, vector được sinh bởi GPU (thường chạy FP16 hoặc lượng tử hóa kiểu GGUF). Khi VRAM trên 12GB, vector được sinh bởi ONNX Runtime trên CPU (thường chạy FP32 hoặc INT8 dynamic quantization).
Dù cùng một kiến trúc model, sai số lượng tử hóa và cách xử lý chuẩn hóa (LayerNorm / L2 Normalization) giữa hai backend khác nhau sẽ làm lệch hướng vector trong không gian nhiều chiều. Khi bạn tính Cosine Similarity giữa một nửa database sinh bởi MI50 và một nửa sinh bởi ONNX CPU, thứ hạng RRF sẽ bị xáo trộn ngẫu nhiên.

3. Lỗ hổng Toán học và Cạm bẫy Thực tế trong Công thức Ebbinghaus

Hãy nhìn kỹ công thức củng cố ký ức (L3 Consolidation) của bạn:

𝑆
(
𝑡
)
=
𝑆
0
⋅
exp
⁡
(
−
𝜆
⋅
Δ
𝑡
)
⋅
(
1
+
ln
⁡
(
1
+
𝑁
hits
)
)
S(t)=S
0
	​

⋅exp(−λ⋅Δt)⋅(1+ln(1+N
hits
	​

))

Công thức này trông rất học thuật, nhưng về mặt giải tích, nó mang lỗi thiết kế nghiêm trọng:

Lỗ hổng 1: Hàm Mũ luôn giết chết Hàm Logarit (Chứng mất trí nhớ sau kỳ nghỉ)

Trong tâm lý học nhận thức (và thuật toán Spaced Repetition thực thụ như SuperMemo/FSRS), mỗi lần một ký ức được gọi lại (
𝑁
hits
N
hits
	​

 tăng), tốc độ suy giảm 
𝜆
λ phải giảm xuống (tức là chu kỳ bán rã dài ra, nằm ở bậc của số mũ).
Nhưng trong công thức của bạn, 
(
1
+
ln
⁡
(
1
+
𝑁
hits
)
)
(1+ln(1+N
hits
	​

)) chỉ là một hệ số nhân tuyến tính bên ngoài số mũ!

Hãy làm một phép tính thực tế:

Giả sử bạn có một ký ức cực kỳ quan trọng về cấu hình hệ thống, đã được truy xuất tới 
𝑁
hits
=
100
N
hits
	​

=100 lần.

Hệ số củng cố của nó là: 
1
+
ln
⁡
(
101
)
≈
5.615
1+ln(101)≈5.615.

Bây giờ, nếu 
Δ
𝑡
Δt là thời gian tính từ lúc tạo ký ức (hoặc bạn nghỉ phép / chuyển sang làm dự án khác trong 3 tuần không đụng tới chủ đề đó), thành phần 
exp
⁡
(
−
𝜆
⋅
Δ
𝑡
)
exp(−λ⋅Δt) sẽ suy giảm theo hàm mũ. Chỉ cần 
𝜆
⋅
Δ
𝑡
≥
3.4
λ⋅Δt≥3.4, ta có 
exp
⁡
(
−
3.4
)
≈
0.033
exp(−3.4)≈0.033.

Khi đó: 
𝑆
(
𝑡
)
=
1.0
⋅
0.033
⋅
5.615
≈
0.185
<
0.20
S(t)=1.0⋅0.033⋅5.615≈0.185<0.20.

Hậu quả: Tiến trình L3 của bạn sẽ xóa vĩnh viễn một ký ức quan trọng từng được dùng 100 lần chỉ vì bạn tạm ngưng làm việc với nó vài tuần! Một "Lifelong Partner" mà cứ chủ nhân đi vắng vài tuần lại xóa sạch ký ức cốt lõi thì không thể gọi là Lifelong.

Lỗ hổng 2: Hiệu ứng "Giàu càng thêm Giàu" từ Nhiễu (Retrieval Poisoning Loop)

Biến 
𝑁
hits
N
hits
	​

 được cộng thêm 1 khi nào? Khi ký ức đó lọt vào Top-K của L1/L2!
Nhưng L1 (Jaccard) và L2 (BM25 không dấu + RRF) chỉ biết khớp từ khóa và ngữ nghĩa bề mặt, chúng không hề biết ký ức được lôi lên có thực sự hữu ích cho câu trả lời cuối cùng hay không.

Những câu giao tiếp chung chung, chứa nhiều từ khóa phổ biến sẽ liên tục lọt vào Top-K ở mọi turn → 
𝑁
hits
N
hits
	​

 tăng vọt → không bao giờ bị xóa.

Ngược lại, những thông tin kỹ thuật cực kỳ đắt giá nhưng hiếm khi được hỏi tới (ví dụ: "Lý do tại sao tháng trước không được bật flag X trong BIOS") sẽ có 
𝑁
hits
=
0
N
hits
	​

=0 trong suốt 2 tháng → bị L3 âm thầm xóa sổ trước khi sự cố lặp lại.

Lỗ hổng 3: Ô nhiễm Bất biến (
𝜆
=
0
λ=0)

Các quy tắc Invariant có 
𝜆
=
0
λ=0 nghĩa là 
𝑆
(
𝑡
)
=
𝑆
0
⋅
(
1
+
ln
⁡
(
1
+
𝑁
hits
)
)
S(t)=S
0
	​

⋅(1+ln(1+N
hits
	​

)) chỉ có tăng chứ không bao giờ giảm. Sau 6 tháng sử dụng, khi kiến trúc dự án của bạn thay đổi (ví dụ từ v3.0 lên v5.0), các quy tắc "bất biến" của thời kỳ cũ vẫn nằm chễm chệ ở đỉnh bảng xếp hạng với điểm 
𝑆
(
𝑡
)
S(t) khổng lồ, trực tiếp mâu thuẫn với các quy tắc mới và gây ra hiện tượng Context Schizophrenia (Tâm thần phân liệt ngữ cảnh) cho Agent.

4. Phác thảo Kiến trúc Cứu hộ (Đề xuất chỉnh sửa cho v4.1)

Nếu muốn Omni-Memory sống sót trong môi trường thực tế trên phần cứng hiện tại, bạn cần phẫu thuật lại 4 điểm sau ngay lập tức:

Thành phần	Thiết kế hiện tại (Lỗ hổng)	Kiến trúc sửa đổi cho v4.1
Luồng tính Embedding	Chạy trên MI50 (port 8080) + Fallback ONNX CPU khi VRAM vượt 12GB.	Tách hoàn toàn khỏi MI50. Chạy cố định 100% một model embedding nhẹ (như bge-small hoặc nomic-embed-text lượng tử hóa INT8) trên CPU qua ONNX Runtime. Tốn chưa tới 300MB System RAM, độ trễ ổn định 5–12ms, giải phóng hoàn toàn 16GB HBM2 của MI50 cho LLM và triệt tiêu 100% nguy cơ WDDM TDR cũng như lệch không gian vector.
SQLite Concurrency	Nhiều luồng / đa phiên ghi trực tiếp vào SQLite WAL + FTS5.	Single-Writer Queue Pattern: Mọi thao tác ghi (từ L1, L2 hay L3) phải đẩy vào một hàng đợi duy nhất (Ring Buffer / Queue) do một tiến trình/luồng Writer độc quyền gom lại và commit theo batch (BEGIN IMMEDIATE). Đặt PRAGMA busy_timeout = 5000; và PRAGMA wal_autocheckpoint = 1000;.
FTS5 Tiếng Việt	Chỉ dùng 1 cột remove_diacritics 2 (mất dấu, loạn nghĩa).	Dual-Column FTS5: Tạo 2 cột trong FTS5: content_exact (remove_diacritics 0, trọng số BM25 cao, ví dụ 10.0) và content_folded (remove_diacritics 2, trọng số thấp 1.0). Từ khớp chính xác cả dấu sẽ luôn đè bẹp từ khớp mò không dấu.
Công thức Ebbinghaus	Nhân 
(1+ln(1+N
hits
	​

)) ở ngoài hàm mũ; xóa cứng khi 
S(t)<0.20.	

Đưa số lần củng cố vào mẫu số của số mũ để kéo dài chu kỳ bán rã:

S(t)=S
0
	​

⋅exp(−
1+αln(1+N
hits
	​

)
λ⋅Δt
	​

)

Đồng thời, khi 
S(t)<0.20, không xóa cứng (DELETE) mà chuyển trạng thái sang Archived (loại khỏi RAM vector scan nhưng giữ lại trên đĩa cho FTS5 tra cứu khi cần).

Giờ đến lượt bạn bảo vệ thiết kế của mình: Thực tế bạn đang chạy hook_runner.py dưới dạng daemon thường trú hay subprocess mỗi turn, và tiến trình tạo embedding trên port 8080 đang chia sẻ tài nguyên với LLM chính theo cơ chế nào?