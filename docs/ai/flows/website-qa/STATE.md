# Trạng thái luồng website-qa

Cập nhật: 2026-11-16

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- Chạy trọn luồng: security → context → làm rõ → analysis → retrieve → stream câu trả lời.
- **Chat production vẫn dùng bảng cũ `doc_chunks`.** Bảng mới `doc_chunks_v2` (F54 296 chunk, F86 Installation 23, catalog 37; đều `draft`) mới chỉ công cụ eval dùng; tích hợp vào chat ("bước 6") chưa làm.
- Đang làm **R-1**: tối ưu bước phân tích (intent, mô tả, model LLM) và định tuyến tra cứu. Kế hoạch 4 giai đoạn A–D đã duyệt; A và phần code của B đã xong. OpenAI hết credit nên eval routing hiện có thể dùng tạm `100milionseek.top` với `HMS_API_KEY`; chỉ là provider eval, không dùng production.
- Production không đổi hành vi trong R-1: mặc định prompt `v1`, mô tả intent `v1`, luật định tuyến `r0`.
- Handoff là scaffold; chưa gửi nguồn/ảnh qua SSE; số `[S#]` đánh lại mỗi lượt. Thay đổi từ catalog tới R-1 **chưa commit**.

## Độ chín từng phần

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| SecurityStage, Context, Prune | có | [security-stage-pipeline.md](../../security-stage-pipeline.md); cột `chat_history.conversation_state` thêm tay, chưa kiểm live |
| Vòng làm rõ | có | Sub-query có cụm lạ bị giữ lại, không tra cứu (lỗi D26, xem R-1) |
| Analysis đa ngôn ngữ | có | Prompt và mô tả intent có phiên bản (`v1`); câu cố định chỉ có `vi`, `en` |
| Luật định tuyến bằng code | có, chỉ eval | `r0` (production) = không luật; `r1`, `r2`, RT-3b chờ đo và duyệt |
| Retrieve hybrid | có, mức test | Production: bảng cũ, không rerank. Repository v2 (eval): FTS sạch, scope cộng điểm 0,003 |
| Eval tra cứu + định tuyến | có | `evals/run_retrieval_eval.py`; hỗ trợ OpenAI và `100milionseek` cho routing; 5 bộ câu (2 bộ nháp chờ duyệt) |
| Handoff; SSE nguồn/ảnh; `retrieved_chunk_ids` | scaffold; chưa có; chưa điền | Cột là `UUID[]`, `doc_chunks.id` là `bigint` |

## R-1: tiến độ, quyết định, kết quả

Kế hoạch đầy đủ (đã duyệt): [p3_r1_routing_plan.md](../../reports/p3_r1_routing_plan.md). Diễn biến: LOG 2026-11-14.

| Giai đoạn | Trạng thái | Còn lại |
|---|---|---|
| Gắn phiên bản prompt | xong | `PROMPT_VERSION = "v1"`, `INTENT_DESC_VERSION = "v1"`; test ghim dấu nội dung |
| A. Công cụ đo + bộ câu | công cụ xong; bộ câu nháp | Toma duyệt `routing_intent.yaml` (120 câu), `dual_source.yaml` (19 câu); mốc 3 bộ còn thiếu |
| B. Luật định tuyến `r1`/`r2` | code + test xong | Đo (cần credit); Toma chọn bản + `target_boost`; chọn RT-3 hay RT-3b |
| C. Mô tả intent + khung prompt `v2` | chưa bắt đầu | Tổng hợp nội dung nguồn → soạn → Toma duyệt câu chữ → đo |
| D. So model LLM | chưa bắt đầu | Toma chốt 2–3 model ứng viên |

Quyết định đã chốt (Toma 2026-11-14): scope cộng điểm 0,003 thay lọc cứng (R-2, đã là mặc định `MatchV2Options`); mọi thay đổi prompt/mô tả intent/luật định tuyến có phiên bản, bản mới chỉ eval chọn tới khi duyệt; D01 sửa bằng luật RT-1 (tìm cả catalog lẫn tài liệu kỹ thuật), không nới nhãn; K09 chấp nhận cả hai intent tra catalog; không làm fallback theo ngưỡng điểm (điểm chunk sai 0,53–0,65 chồng lên chunk đúng).

Kết quả đo (prompt `v1`, luật `r0`, gpt-4.1-mini, 3 lần mỗi câu; thư mục trong `data/retrieval_eval/`):

| Bộ câu | Đúng cả ba web1 / web2 | Ổn định | Ghi chú |
|---|---|---|---|
| 40 câu (`20261114-154614-baseline-v1-r0-diverse40`) | 0,867 / 0,867 | 0,925 / 0,95 | Nhiễu giữa các lần 2,5–5 điểm %; web2 scope 0,003: recall@5 0,853, MRR 0,798. Ước tính có luật (không gọi LLM, chưa phải số đo): domain đúng 0,90 → 1,0 |
| 120 câu nháp (`20261114-155459-draft-v1-r0-routing120`) | 0,936 / 0,942 | 0,975 / 0,983 | Nhóm tên board/phụ kiện 0,29 / 0,71 |
| 14 câu, catalog 20, hai nguồn 19 | **chưa có** | — | Dừng vì hết credit |

## Vấn đề mở

| ID | Vấn đề |
|---|---|
| **B-1** | **Tài khoản OpenAI hết credit** (429 `credit_balance_exhausted`, 2026-11-14). Chặn mọi phép đo; dịch vụ chat dùng cùng key cũng lỗi cho tới khi nạp |
| R-1 | Bước phân tích chọn sai intent → sai nguồn; còn nguyên ở production (`r0`): (a) câu có mã hoặc hỏi "là gì"/"cài ở đâu"/"công thức" bị xếp `lookup.product_info` → chỉ tìm catalog (D21, D30, Q8, Q9, R004, R008, R022); (b) câu thông số có câu trả lời ở manual chỉ tìm catalog (D01, Q12, D39); (c) tên board/phụ kiện/thiết bị hãng khác bị coi là model lạ → **không tra cứu** (D26, R107–R114); (d) vận hành ↔ xử lý sự cố (D06), phụ kiện ↔ công ty (R104). Luật `r1`/`r2` nhắm (a)–(c), chưa đo |
| R-1a/b/c | (a) Hai nguồn định nghĩa intent lệch nhau: `desc` (registry) và `<intent_rules>` (quy tắc 4 đòi "CÁC BƯỚC") → sửa ở giai đoạn C. (b) Chọn RT-3 (danh sách `non_model_terms`, nháp: 08_RLTR, RBT-01) hay RT-3b (cụm lạ không có model gần giống; thăm dò ủng hộ) — chờ Toma. (c) "Đúng cả ba" vẫn tính sai khi intent lệch nhãn dù tìm đúng nguồn → sau RT-1 quyết định theo "domain đúng" + `ngu_canh` |
| R-2, R-4 | Scope cộng điểm đã áp (khi intent chắc chắn đúng thì lọc cứng vẫn nhỉnh hơn, câu S8). `fts_clean` đã bật ở repository v2, vẫn đo song song `no_fts_clean` |
| R-3 | `coverage` của registry viết cứng (chỉ F86 có `technical_docs`); eval phải thêm F54 trong bộ nhớ; nạp tài liệu mới phải sửa code |
| C-1, C-2 | Registry thêm `10S`, `10i` (tên tạm, chờ CRM). Catalog 7 bộ điều khiển đã nạp (37 chunk, draft, chưa gắn hình); câu tiếng Việt vs nhãn tiếng Anh xếp thấp (K09 hạng 3, K10, K19) → `--vi-keywords` **chờ Toma**. Còn thiếu servo, board (trang 22), phụ kiện (trang 23), thông tin công ty (D39 chờ dữ liệu board) |
| E-05 | Nhánh FTS của `match_doc_chunks` bỏ mọi dòng khi bộ lọc model là mảng rỗng; trên Supabase thật cả hai nhánh trả rỗng với `[]` ([p2_chunk_contract.md](../../reports/p2_chunk_contract.md)) |
| L-2, L-4 | Supabase thật chưa áp `migrate_product_models_crm.sql` (check `product_models` còn ASTRO_*, `embedding` nullable; [p2_doc_chunks_schema_review.md](../../reports/p2_doc_chunks_schema_review.md) §1); bảng cũ có 0 dòng `technical_docs` dù registry khai báo coverage F86 |
| D-008 | Chỉ tìm trên chunk con/độc lập ([decisions.md](../../decisions.md)); bảng cũ chưa có cột `chunk_role` + điều kiện trong `match_doc_chunks` |
| H1, H6, T-1 | Handoff không tạo ticket; `[S#]` không lưu qua lượt; trace production chưa ghi phiên bản prompt/luật định tuyến (mới có log và `warnings`) |
| — | Mã model dính chữ tiếng Việt ("F86có") không được nhận; capabilities của F86E, 6AHE, 6AVE, 10iV, 10iVE là tạm |

## Kết quả kiểm gần nhất

2026-11-14, từ `backend/`: `pytest tests` → 1120 passed, 14 skipped; `pytest tests\doc_ingest` (venv ingest) → 376 passed; `scripts\check_ai_docs.py` → đạt.
Chưa chạy lại đợt này (không đổi frontend): `npm test` widget-backend, `npm run build`, `npm run lint` (số 2026-11-11: 22 pass; build đạt; lint 429 lỗi sẵn có).

## Bước tiếp theo

1. **Toma:** nạp credit OpenAI; duyệt `evals/retrieval_cases/routing_intent.yaml` và `dual_source.yaml` (nên thêm 20–30 câu `test` theo cách hỏi thật); chọn RT-3 hay RT-3b; quyết `--vi-keywords`.
2. Khi có credit, từ `backend/`: `evals\run_retrieval_eval.py --cases evals\retrieval_cases\<bộ>.yaml --mode website --repeat 3 --label <nhãn>` cho mốc còn thiếu (`sample_f54_f86`, `catalog_f54_astro`, `dual_source`); rồi thêm `--routing-version r1` / `r2` / `RT-1+RT-2+RT-3b` trên cả 5 bộ (bộ 120 câu dùng `--mode routing`). Biến thể `sb0.003_tb0`, `sb0.003_tb0.005` để chọn `target_boost`. Quyết định theo `ngu_canh`, MRR web2, "domain đúng"; chênh lệch dưới biên nhiễu không tính.
3. Cổng B: Toma chọn bản luật; đổi `ROUTING_VERSION` mặc định cùng lúc tích hợp `doc_chunks_v2` vào chat.
4. Giai đoạn C (prompt `v2`), rồi D (so model bằng `--analysis-model`).
5. Sau R-1: tích hợp `doc_chunks_v2` vào chat, sửa E-05, SSE nguồn/ảnh, handoff thật (H1), lưu `[S#]` (H6).
