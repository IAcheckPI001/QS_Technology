# Báo cáo kiểm thử định tuyến `v1/r0` — 2026-11-14

## Phạm vi và nguồn dữ liệu

- Run: `data/retrieval_eval/20261114-155459-draft-v1-r0-routing120/`.
- Bộ câu: `backend/evals/retrieval_cases/routing_intent.yaml`; run ghi nhận **120 câu**, `split=all`.
- Cấu hình: `gpt-4.1-mini`; prompt `v1`, mô tả intent `v1`, `n_examples=4`, SHA-256 prefix `8e431a735a4c`; routing `r0` (không luật định tuyến bằng code); 3 lần/câu.
- Chế độ `routing`: mỗi câu chạy ở hai ngữ cảnh (`web1` chưa có model; `web2` model đã có trong hội thoại), tổng 720 lượt phân tích. Retriever giả lập; **run này chỉ đánh giá phân tích/định tuyến, không đo chất lượng tìm chunk**.
- F54 được bổ sung coverage `technical_docs` trong bộ nhớ cho eval. Không thay đổi coverage production.
- Kết quả chi tiết: `data/retrieval_eval/20261114-155459-draft-v1-r0-routing120/report.md` và `results.json`.

## Kết quả tổng

| Chỉ số | Web1 | Web2 |
|---|---:|---:|
| Intent đúng | 0,975 | 0,961 |
| Route đúng | 0,953 | 0,981 |
| Domain đúng | 0,975 | 0,969 |
| Intent + route + domain cùng đúng | 0,936 | 0,942 |
| Ổn định giữa ba lần | 0,975 | 0,983 |
| Biên tỷ lệ đúng cả ba theo từng lần | 0,933–0,942 | 0,933–0,950 |

Không ghi nhận lỗi phân tích. Độ trễ: p50 **1.402 ms**, p95 **1.653 ms**, cao nhất **2.812 ms** (720 lần gọi bước phân tích).

## Độ phủ bộ câu

Các nhóm `cap:*` được cân để thử ranh giới intent; tag kiểu người hỏi, mã, tiếng Anh, câu không dấu và thiếu model là các nhãn chồng lấp.

| Nhóm chủ đề | n | Web1: cả ba đúng (intent đúng) | Web2: cả ba đúng (intent đúng) |
|---|---:|---:|---:|
| Thông số / tham số | 20 | 0,950 (0,950) | 0,900 (0,900) |
| Cổng có sẵn / cổng đấu nối | 16 | 0,938 (0,938) | 0,938 (0,938) |
| Công ty / chuyển người | 12 | 1,000 (1,000) | 1,000 (1,000) |
| Một model / danh mục | 12 | 1,000 (1,000) | 1,000 (1,000) |
| Vận hành / sự cố | 14 | 1,000 (1,000) | 1,000 (1,000) |
| Vận hành / cấu hình | 12 | 1,000 (1,000) | 0,917 (0,917) |
| Lắp đặt / cấu hình | 12 | 1,000 (1,000) | 1,000 (1,000) |
| Danh mục / so sánh | 8 | 1,000 (1,000) | 0,917 (0,917) |
| Phụ kiện | 8 | 0,292 (0,875) | 0,708 (1,000) |
| Đối chứng | 6 | 1,000 (1,000) | 1,000 (1,000) |

Tag chồng lấp theo report: khách hàng 75, nhân viên 45, câu không dấu 11, có mã 13, tiếng Anh 12, thiếu model 29 và đối chứng 6.

## Các xu hướng và lỗi nổi bật

### Nhóm intent ổn định

- Các cặp vận hành/sự cố, lắp đặt/cấu hình, một model/danh mục và công ty/chuyển người đạt 100% cả ba tiêu chí trong cả hai ngữ cảnh.
- Nhóm cổng/đấu nối đạt 0,938; nhóm thông số/tham số đạt 0,950 ở web1 và 0,900 ở web2.
- Nhóm vận hành/cấu hình giảm ở web2 do R065 (“Nhập bù chiều dài dao…”) được gán `guide.configuration` thay vì nhãn kỳ vọng `guide.operation` cả ba lần. Cần xem lại ranh giới nhãn vì cách diễn đạt có thể hợp lý với cả hai intent.

### Nhầm intent/domain nhất quán

- R008 (công thức số xung/mm) bị chọn `lookup.product_info` / `product_catalog` thay cho `guide.configuration` / `technical_docs`: web1 3/3, web2 3/3.
- R022 (cổng CN5 dùng để làm gì) bị chọn `lookup.product_info` / `product_catalog` thay cho `guide.installation` / `technical_docs`: web1 3/3, web2 3/3.
- R004 (câu không dấu về tham số #12100, web2) cũng bị chọn `lookup.product_info` / `product_catalog` cả ba lần.
- R104 (hỏi QS có phụ kiện gì) ở web2 dao động: `lookup.company_info` 2/3 lần, `lookup.product_catalog` 1/3. Đây vừa là vấn đề chọn intent vừa là ranh giới nhãn cần rà.
- R110 (RBT-01 có dùng với F54 được không) ở web1 bị chọn `other.out_of_scope` cả ba lần. Ở web2 intent được chấp nhận (`lookup.product_info`) nhưng truy vấn bị giữ do `unknown_product_model`.

### Intent đúng nhưng route/thực thi không tìm

- Nhóm phụ kiện là điểm yếu chính của tỷ lệ “cả ba đúng”: **intent accuracy 0,875/1,000**, nhưng tỷ lệ cả ba chỉ **0,292/0,708** (web1/web2).
- Với R107, R112, R113 và một số lần R108/R109/R114, intent và domain đúng nhưng `clarify_reason=unknown_product_model`; pipeline không phát lệnh tìm (`searched=false`). Vì evaluator coi truy vấn không thực sự được gửi là route sai, điểm tổng thấp hơn điểm intent.
- Đây chủ yếu là vấn đề entity resolution/giữ truy vấn quanh tên board, phụ kiện hoặc thiết bị (“08_RLTR”, “RBT-01”, “driver servo QS”), không phải LLM luôn chọn sai intent.

## Giới hạn diễn giải

1. Bộ YAML hiện ghi chờ duyệt và run chạy `split=all`; các chỉ số tổng gồm cả phần `dev` lẫn `test`, không phải điểm test holdout riêng.
2. Report của run có R001–R120 và tag đối chứng n=6; YAML hiện tại có R001–R119, 71 `dev` + 48 `test`, thiếu R120. Artifact `results.json` còn kết quả R120 (đúng cả ba lần ở hai ngữ cảnh), nhưng không lưu nguyên văn câu hỏi. Vì vậy không thể tái lập hoàn toàn run 120 câu từ YAML hiện tại.
3. Độ chính xác định tuyến không phải recall/MRR tìm kiếm; run `routing` dùng retriever giả và không kiểm tra nội dung `doc_chunks_v2`.
4. Các tỷ lệ đo trên bộ câu có chủ đích, không đại diện phân bố câu hỏi tự nhiên. F54 chiếm phần lớn câu có model; nhóm phụ kiện chỉ có 8 câu.

## Kết luận

Với `v1/r0`, đầu ra intent và route nhìn chung ổn định trên phần lớn nhóm đã thiết kế. Các lỗi tập trung ở câu chuyển ranh giới thông số–tham số, cổng–đấu nối và phụ kiện; trong nhóm phụ kiện cần phân biệt lỗi chọn intent với lỗi entity resolution làm pipeline không thực sự tìm. Đây là baseline định tuyến trên bộ câu nháp, chưa phải đánh giá retrieval hoặc kết quả production.
