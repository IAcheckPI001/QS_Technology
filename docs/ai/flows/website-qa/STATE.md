# Trạng thái luồng website-qa

Cập nhật: 2026-11-26 (đối chiếu code, git và các báo cáo trong `data/retrieval_eval/`)

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- Chạy trọn luồng: security → context → làm rõ → analysis → retrieve → stream câu trả lời.
- **Chat đã chuyển hẳn sang `doc_chunks_v2`** (D-009 bước 6, 2026-11-19; đã nằm trong `feature/deploy_ai_service`, nhánh triển khai chính, HEAD `846b5fe` trùng `origin`): `main.py` dựng `DocChunkV2Repository(MatchV2Options(approved_only=RETRIEVAL_APPROVED_ONLY))` cho cả luồng website lẫn tool `product_docs_ask`; `DocChunkRepository` đã xoá, bảng cũ `doc_chunks` chỉ giữ để đối chiếu. Coverage `technical_docs` nạp từ DB lúc khởi động.
- **Cảnh báo:** mọi chunk v2 đang `draft` (2026-11-25: 1.203 dòng, gồm F54, F86, catalog và 847 chunk CRM; 0 approved). `RETRIEVAL_APPROVED_ONLY` mặc định `true` → chat **không tìm thấy tài liệu nào** cho tới khi chunk được duyệt `approved`. Dev/staging đặt `RETRIEVAL_APPROVED_ONLY=false`.
- Đang làm **R-1**: tối ưu bước phân tích (intent, mô tả, model LLM) và định tuyến tra cứu. Kế hoạch 4 giai đoạn A–D đã duyệt; A và phần code của B đã xong. OpenAI hết credit nên eval routing hiện có thể dùng tạm `100milionseek.top` với `HMS_API_KEY`; chỉ là provider eval, không dùng production.
- **Đối tượng xem (D-014, 2026-11-21, đã commit `4602e94` trên `feature/deploy_ai_service`; code khớp: `retrieval/audience.py`, `ExecutionStage`; SQL đã áp trên Supabase, xác nhận 2026-11-25: cột `audience` và `p_audiences` có; 1.203 chunk đều `public`):** website chỉ tra chunk `audience='public'`, kênh CRM cả `internal`; `RetrievalRequest.audiences` do `ExecutionStage` đặt theo kênh, mặc định `public`. Môi trường Supabase khác phải áp `backend/sql/doc_chunks_v2.sql` trước khi deploy. Prompt trả lời có `<answer_format>` (chưa đo). **Giai đoạn B:** event SSE `sources` (nguồn trích dẫn + ảnh, URL ký, bucket private `doc-assets`) sau cờ `CHAT_SOURCES_ENABLED` mặc định tắt; chưa đẩy ảnh nào lên bucket.
- **Widget (WU-17 đợt 1, commit `fe819ea`, merge `a1de8e9` vào `feature/deploy_ai_service`):** câu trả lời render GFM (bảng) qua `src/components/Markdown.jsx` + `remark-gfm`; `[S#]` là huy hiệu tròn có chú thích "tiêu đề · trang" lấy từ event `sources`; `npm test` 95 đạt, build đạt; đã thấy huy hiệu trong một lượt thật (backend dev, 2026-11-25). Lịch sử tải lại chưa có nguồn/ảnh (WU-17 đợt 2).
- Production không đổi hành vi trong R-1: mặc định prompt `v1`, mô tả intent `v1`, luật định tuyến `r0`. Handoff là scaffold; số `[S#]` đánh lại mỗi lượt.

## Độ chín từng phần

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| SecurityStage, Context, Prune | có | [security-stage-pipeline.md](../../security-stage-pipeline.md); cột `chat_history.conversation_state` thêm tay, chưa kiểm live |
| Vòng làm rõ | có | Sub-query có cụm lạ bị giữ lại, không tra cứu (lỗi D26, xem R-1) |
| Analysis đa ngôn ngữ | có | Prompt và mô tả intent có phiên bản (`v1`); câu cố định chỉ có `vi`, `en` |
| Luật định tuyến bằng code | có, chỉ eval | `r0` (production) = không luật; `r1`, `r2`, RT-3b chờ đo và duyệt |
| Retrieve hybrid | có, mức test | Production và eval cùng `DocChunkV2Repository`: FTS sạch, scope cộng điểm 0,003, chunk cha thật, không rerank, không nhánh mã. Chưa kiểm trên Supabase thật sau khi chuyển |
| Coverage `technical_docs` | nạp từ DB | `main.load_technical_coverage` → `registry.extend_technical_coverage` (chỉ thêm; lỗi DB giữ registry tĩnh). Eval gọi cùng hàm, tính cả draft |
| Eval tra cứu + định tuyến | có | `evals/run_retrieval_eval.py`: chế độ `core` (biến thể `match_doc_chunks_v2`, không LLM), `website` (pipeline thật, lượt web1/web2), `routing` (retriever giả), `all`; `--repeat`, `--split`, `--analysis-model`, `--routing-version`, `--scope-sweep`; `approved_only=False`; OpenAI và `100milionseek` (chỉ routing); 5 bộ câu (2 bộ nháp chờ duyệt). Eval agent (`run_crm_agent_eval`, `compare_agent_models`) dùng cấu hình tra cứu như production. Mới (GD0): `ctx_precision`/`nhieu`, trường `source`/`facts`/`perturb_of`/`expect_abstain`; `evals/run_generation_eval.py` (oracle/real, kiểm tự động `gen_checks.py`, bảng chấm tay `grading.py`); `scripts/export_chat_log.py` |
| Handoff; SSE nguồn/ảnh; `retrieved_chunk_ids` | scaffold; có sau cờ, chưa kiểm thật; chưa điền | Cột là `UUID[]`, `doc_chunks_v2.id` là `bigint` |

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
| 120 câu nháp ([báo cáo](../../reports/website_qa_routing_eval_v1_r0_2026-11-14.md); `20261114-155459-draft-v1-r0-routing120`) | 0,936 / 0,942 | 0,975 / 0,983 | Nhóm phụ kiện 0,29 / 0,71; routing-only, split=all |
| 14 câu, catalog 20, hai nguồn 19 | **chưa có** | — | Dừng vì hết credit |
| 48 câu `split=test` của `routing_intent.yaml`, luật **`r2`** (RT-1..RT-4), `deepseek-v4.1-flash-free` qua 100milionseek, 1 lần, `--mode routing` (`20261116-184412`) | 0,542 / 0,500 | 1,0 / 1,0 (chỉ 1 lần, không có biên nhiễu) | Intent đúng 0,917 / 0,958; route 0,708 / 0,688; domain 0,542 / 0,5. 1 lỗi `analysis_invalid_output` (R108). Nhầm intent: R022, R040 (catalog → handoff), R078, R108. Nhóm `cong_co_san~cong_dau_noi` 0,5. Độ trễ p50 11,4 s, p95 72,9 s. **Không so được với `r0`/gpt-4.1-mini** (khác model, khác tập câu, chưa có đối chứng `r0` cùng model) nên chưa kết luận. Các run 11-16 còn lại là thử công cụ 1 câu (Phi-3 hết thời gian; deepseek `r0`), không phải số đo |

## Vấn đề mở

| ID | Vấn đề |
|---|---|
| **B-1** | **Tài khoản OpenAI hết credit** (429 `credit_balance_exhausted`, 2026-11-14). Chặn mọi phép đo; dịch vụ chat dùng cùng key cũng lỗi cho tới khi nạp |
| R-1 | Bước phân tích chọn sai intent → sai nguồn; còn nguyên ở production (`r0`): (a) câu có mã hoặc hỏi "là gì"/"cài ở đâu"/"công thức" bị xếp `lookup.product_info` → chỉ tìm catalog (D21, D30, Q8, Q9, R004, R008, R022); (b) câu thông số có câu trả lời ở manual chỉ tìm catalog (D01, Q12, D39); (c) tên board/phụ kiện/thiết bị hãng khác bị coi là model lạ → **không tra cứu** (D26, R107–R114); (d) vận hành ↔ xử lý sự cố (D06), phụ kiện ↔ công ty (R104). Luật `r1`/`r2` nhắm (a)–(c), chưa đo |
| R-1a/b/c | (a) Hai nguồn định nghĩa intent lệch nhau: `desc` (registry) và `<intent_rules>` (quy tắc 4 đòi "CÁC BƯỚC") → sửa ở giai đoạn C. (b) Chọn RT-3 (danh sách `non_model_terms`, nháp: 08_RLTR, RBT-01) hay RT-3b (cụm lạ không có model gần giống; thăm dò ủng hộ) — chờ Toma. (c) "Đúng cả ba" vẫn tính sai khi intent lệch nhãn dù tìm đúng nguồn → sau RT-1 quyết định theo "domain đúng" + `ngu_canh` |
| R-2, R-4 | Scope cộng điểm đã áp (khi intent chắc chắn đúng thì lọc cứng vẫn nhỉnh hơn, câu S8). `fts_clean` đã bật ở repository v2, vẫn đo song song `no_fts_clean` |
| R-3 | Đã xử lý phần `technical_docs` (2026-11-19): coverage nạp từ `doc_chunks_v2` lúc khởi động theo `approved_only`. Còn viết cứng: `product_catalog`, interface lấy từ `capabilities` (tạm cho vài model); model mới nạp chỉ có hiệu lực sau khi khởi động lại dịch vụ |
| C-1, C-2 | Registry thêm `10S`, `10i` (tên tạm, chờ CRM). Catalog 7 bộ điều khiển đã nạp (37 chunk, draft, chưa gắn hình); câu tiếng Việt vs nhãn tiếng Anh xếp thấp (K09 hạng 3, K10, K19) → `--vi-keywords` **chờ Toma**. Còn thiếu servo, board (trang 22), phụ kiện (trang 23), thông tin công ty (D39 chờ dữ liệu board) |
| E-05, L-2, L-4, D-008 | Thuộc bảng cũ `doc_chunks`; chat không còn dùng bảng này từ 2026-11-19. `match_doc_chunks_v2` đã sửa lọc model rỗng (E-05) và chỉ tìm trên chunk con/độc lập (D-008) |
| A-1 | Chưa có quy trình đưa chunk v2 sang `approved` → với cấu hình production mặc định, chat không có tài liệu. Việc của luồng doc-ingest (cổng 2b/2c, verdict) |
| H1, H6, T-1 | Handoff không tạo ticket; `[S#]` không lưu qua lượt; trace production chưa ghi phiên bản prompt/luật định tuyến (mới có log và `warnings`) |
| — | Mã model dính chữ tiếng Việt ("F86có") không được nhận; capabilities của F86E, 6AHE, 6AVE, 10iV, 10iVE là tạm |

## Kết quả kiểm gần nhất

Eval tra cứu: số đo gần nhất 2026-11-16 (bảng R-1), chưa chạy lại sau khi chat chuyển v2 (11-19) và thêm `audience` (11-21). **Nhãn chunk của bộ cũ đã lệch DB sau khi nạp lại (đối chiếu 2026-11-25, chunk `expected` khớp: `sample_f54_f86` 0/24, `diverse_40` 3/84, `scope_f54` 0/23, `dual_source` 8/25; chỉ `catalog_f54_astro` 24/24)** → số đo cũ không tái lập, phải gắn nhãn lại. Kế hoạch đo mới (bản tối thiểu, không LLM-judge): [báo cáo](../../reports/website_qa_retrieval_eval_plan_2026-11-25.md) §9; GD0 (công cụ) xong 11-25 — smoke trên 3 câu chạy được, `pytest tests\chatbot tests\api` 700 đạt, 1 lỗi có sẵn `test_sources` (phụ thuộc `.env` cục bộ); GD1 (bộ vàng 60 câu, QS) chưa bắt đầu.
2026-11-19 (chuyển v2, worktree nhánh `claude/retrieval-v2-chat`, `DATABASE_URL` giả): `pytest tests\chatbot tests\api` → 594 passed; `pytest tests` → 1077 passed, 14 skipped, 1 failed (`test_f86_baseline_csv_unchanged`: worktree checkout CSV bằng CRLF do `core.autocrlf=true`, blob trong git đúng hash; không liên quan thay đổi); `check_ai_docs` đạt. Chưa smoke trên Supabase thật.
2026-11-26 (WU-17 đợt 3A, chỉ frontend): `npm test` → 106 đạt; build đạt; lint toàn repo còn lỗi có sẵn (file widget 0). Widget có dòng hoạt động AI (chờ event `status` từ backend), giọng nói (Web Speech API), nút thêm ảnh sau `VITE_CHAT_IMAGE_INPUT` (chưa gửi ảnh lên máy chủ).

## Bước tiếp theo

1. **Toma:** nạp credit OpenAI; duyệt `evals/retrieval_cases/routing_intent.yaml` và `dual_source.yaml` (nên thêm 20–30 câu `test` theo cách hỏi thật); chọn RT-3 hay RT-3b; quyết `--vi-keywords`. QS viết/gắn nhãn bộ vàng v1 vào `evals/retrieval_cases/gold_v1.yaml` (GD1).
2. Khi có credit, từ `backend/`: `evals\run_retrieval_eval.py --cases evals\retrieval_cases\<bộ>.yaml --mode website --repeat 3 --label <nhãn>` cho mốc còn thiếu (`sample_f54_f86`, `catalog_f54_astro`, `dual_source`); rồi thêm `--routing-version r1` / `r2` / `RT-1+RT-2+RT-3b` trên cả 5 bộ (bộ 120 câu dùng `--mode routing`). Biến thể `sb0.003_tb0`, `sb0.003_tb0.005` để chọn `target_boost`. Quyết định theo `ngu_canh`, MRR web2, "domain đúng"; chênh lệch dưới biên nhiễu không tính.
3. Cổng B: Toma chọn bản luật rồi đổi `ROUTING_VERSION` mặc định (luật vẫn `r0`). Sau đó giai đoạn C (prompt `v2`), D (so model bằng `--analysis-model`).
4. Smoke v2: bước khởi động đã kiểm trên Supabase thật (2026-11-19: coverage thêm F54, `approved_only=False`); còn lượt thật có tra cứu — sau khi nạp credit hỏi một câu F54, một câu F86 → trace có `db.match_doc_chunks`, có `[S#]`. Duyệt chunk `approved` trước khi bật production.
5. D-014: áp SQL `audience`, chạy `publish-assets --apply` cho một tài liệu, bật `CHAT_SOURCES_ENABLED`, smoke lượt thật có ảnh; chạy `npm test/lint/build`. Sau R-1: nhánh mã `codes`, handoff thật (H1), lưu `[S#]` (H6).
