# Website-qa: thang đo và kế hoạch đánh giá tra cứu, phân tích, trả lời (2026-11-25)

Nguồn số liệu: 109 lượt trong `chat_history` + `chat_traces` (2026-11-20 → 2026-11-25; 63 website, 46 crm; 58 lượt website có
`retrieval_snapshot.chunks`). Chỉ đọc DB, chưa chấm nhãn tay. Đây là kế hoạch, chưa phải kết luận chất lượng.

## 1. Hiện trạng các ngưỡng

| Tham số | Giá trị | Đã đo bằng eval? |
|---|---|---|
| `RETRIEVAL_MIN_SIMILARITY` (cosine) | 0,25 | **Chưa.** Kế hoạch P6 (0,25/0,35/0,45) chưa chạy. Dữ liệu thật: `top_score` thấp nhất 0,466, nên 0,25 gần như không lọc gì (số chunk "qua ngưỡng" median 14, p10 11) |
| `vector_k`, `fts_k` = 20, `rrf_k` = 60, `final_chunk_top_k` = 6 | mặc định | Chưa quét; chỉ so biến thể FTS clean / scope |
| `scope_boost` | 0,003 | Có (R-2, 2026-11-14, 40 câu, nhiễu 2,5–5 điểm %) |
| `spec_boost` | 0,005 | Chưa thấy số đo |
| `target_boost` (RT) | 0,003/0,005 | Biến thể có sẵn, chưa chạy |
| Fallback theo ngưỡng | không làm | Quyết định dựa trên điểm chunk sai 0,53–0,65 chồng chunk đúng |

Kết luận: các ngưỡng *lọc chunk thấp điểm* **chưa được chọn bằng đánh giá**; chỉ scope_boost có số đo.

## 2. Bước phân tích LLM (chuẩn hóa câu, intent, entities)

Đã đo: 40 câu và 120 câu `v1/r0` gpt-4.1-mini (đúng cả ba 0,87–0,94), 48 câu test `r2` deepseek (0,54/0,50). Production dùng `gpt-4o-mini`
(trace thật: p50 2,7 s, ~4,8k token vào, 90% là cache). **Chưa đo trên model production**, chưa đo trên câu thật (gõ không dấu, sai
chính tả, câu ghép), chưa đo chất lượng `normalized_query` (viết lại câu) riêng.

## 3. Chunk đưa cho LLM: đúng/không liên quan

Chưa có nhãn nên **chưa biết**. Chỉ có proxy "chunk được trích `[S#]`" (58 lượt website): đưa 5 chunk/lượt (có lượt 8–10), tỉ lệ được trích
**0,48**; hạng 1 được trích 0,84, hạng 5 chỉ 0,31, hạng 9 chỉ 0,14. Trích dẫn ≠ đúng; chunk không trích có thể vẫn đúng hoặc là nhiễu.
Chỉ ~65 chunk (lượt từ 11-25) có `similarity` lưu; lượt cũ không có.

## 4. Thang đo

**A. Tra cứu (cần nhãn chunk đúng theo câu; dùng `run_retrieval_eval.py`)**
- Recall@k (k=1,3,5,6), MRR, Hit@context (chunk đúng nằm trong top `final_chunk_top_k`).
- **Context precision** = số chunk liên quan ÷ số chunk đưa vào prompt; **noise chunks/lượt** = số chunk không liên quan; **Context recall** = tỉ lệ
  *sự kiện cần để trả lời* có trong ngữ cảnh (chấm theo danh sách fact vàng của câu).
- Phân bố điểm: AUC / khoảng chồng điểm của chunk đúng vs sai (quyết định ngưỡng có ích hay không); tỉ lệ câu "không có tài liệu" (no_hits) đúng.

**B. Phân tích (bộ `routing_intent.yaml` + câu thật)**
- Intent đúng, route đúng (retrieve/clarify/handoff/no_docs), domain đúng, models/entities (precision/recall/F1 theo từng thực thể: model, interface, spec), đúng cả ba,
  ổn định giữa các lần (`--repeat 3`), tỉ lệ lỗi phân tích, độ trễ p50/p95, chi phí/lượt.
- `normalized_query`: giữ đủ ý/không bịa (chấm 0/1 theo rubric), có thêm model từ ngữ cảnh đúng không.

**C. Trả lời (LLM-judge + người)**
- Faithfulness (mọi khẳng định có trong chunk), Answer correctness (so fact vàng), Completeness (đủ fact), Citation precision/recall (`[S#]` trỏ đúng chunk),
  Abstention đúng (không có dữ liệu thì nói không biết, không bịa), Clarification đúng, format (bảng/danh sách), ngôn ngữ.

**D. Vận hành:** latency p50/p95, token, cost/lượt, tỉ lệ lỗi (`analysis_error`, `provider_error`).

## 5. Kế hoạch (thứ tự thực hiện)

1. **Bộ vàng (chặn mọi bước sau).** Lấy 60–100 câu: ~50% từ `chat_history` thật (đã ẩn thông tin cá nhân), ~50% từ bộ YAML hiện có; gắn nhãn: model, intent, domain, chunk
   đúng (`content_hash`+`section_path`), danh sách fact vàng, loại câu (thông số, đấu nối, so sánh, mơ hồ, ngoài phạm vi, không dấu). Toma/QS duyệt; chia dev/test.
2. **Chấm chunk của lượt thật (rẻ, làm ngay):** 58 lượt website × chunk đã lưu trong snapshot → nhãn liên quan/không (người hoặc LLM-judge rồi người kiểm 20%) → ra
   context precision và noise chunk/lượt đầu tiên.
3. **Quét tham số tra cứu** trên bộ vàng, `--mode core`/`website`, 3 lần: `min_similarity` {0,25; 0,35; 0,45; 0,5}, `final_chunk_top_k` {3,4,5,6,8}, `vector_k/fts_k` {10,20,40},
   `rrf_k` {20,60}, `spec_boost` {0, 0,005, 0,01}, `target_boost`. Chọn theo: Recall@k không giảm quá biên nhiễu, context precision tăng, rồi mới tới token. Không đổi mặc định khi chênh lệch dưới biên nhiễu.
4. **Thử nghiệm cắt theo khoảng cách điểm** (gap-cut, cắt chunk sau điểm giảm mạnh) và **rerank** chỉ như biến thể eval; chỉ chọn nếu vượt precision ≥ +10 điểm % mà recall không giảm.
5. **Phân tích:** chạy bộ 120 câu + câu thật trên `gpt-4o-mini` (production) với `v1/r0`, rồi `r1/r2`, `--repeat 3`; so thêm 2–3 model ứng viên (giai đoạn D). Đối chứng cùng model mới kết luận.
6. **Trả lời:** chạy end-to-end bộ vàng, LLM-judge (model khác model sinh) + người chấm mẫu 30%; đo Faithfulness, Correctness, Citation, Abstention.
7. **Giám sát liên tục:** lưu `similarity`, `chunk_id`, phiên bản prompt/luật vào snapshot/trace; báo cáo hằng tuần trên lượt thật (precision proxy, tỉ lệ clarify/no_hits, lỗi); cổng hồi quy trước mỗi lần đổi ngưỡng/prompt.

## 6. Ngưỡng chấp nhận đề xuất (khởi điểm, Toma duyệt)

Recall@6 ≥ 0,90; context precision ≥ 0,6 (hiện proxy ≤ 0,48); đúng cả ba ≥ 0,90 trên model production; faithfulness ≥ 0,95; abstention đúng ≥ 0,9; lỗi phân tích < 1%.

## 7. Giới hạn của dữ liệu hiện có

- Trace chỉ chứa metadata (không có điểm từng chunk); điểm từng chunk chỉ có trong `retrieval_snapshot` từ ngày 2026-11-25; `retrieved_chunk_ids` đang rỗng.
- 109 lượt trên 6 ngày, phần lớn do đội phát triển thử (F54, F86, 6AH/6AV) — không đại diện khách thật.
- Chunk v2 đều `draft`; chạy với `RETRIEVAL_APPROVED_ONLY=false`.

## 8. Kế hoạch chi tiết và chống overfit

Mọi con số dưới đây là **đề xuất khởi điểm**, chưa được duyệt; thời gian là ước lượng thô.

### 8.1 Cỡ mẫu và độ tin cậy (quyết định cỡ bộ test)

Với tỉ lệ đúng ~0,8, khoảng tin cậy 95% là ±11 điểm % khi n = 50, ±8 khi n = 100, ±6 khi n = 150. Hệ quả: bộ test 50 câu chỉ thấy được chênh lệch
lớn; so hai biến thể phải dùng **cùng bộ câu và kiểm định ghép cặp** (McNemar cho đúng/sai, bootstrap 1.000 lần cho MRR/precision), báo khoảng tin cậy, không
báo một con số. Chênh lệch nhỏ hơn biên nhiễu giữa các lần chạy (`--repeat 3`) hoặc nhỏ hơn khoảng tin cậy thì coi như không khác.

### 8.2 Bộ vàng: 120 câu gốc + biến thể

| Nhóm câu | Số câu | Ghi chú |
|---|---|---|
| Thông số, kích thước, tính năng | 20 | có số liệu cụ thể để chấm fact |
| Đấu nối, lắp đặt, cổng, sơ đồ | 20 | nhiều bảng và hình |
| Cấu hình, vận hành | 15 | quy trình nhiều bước |
| Xử lý lỗi, báo động | 10 | |
| So sánh 2–3 model | 12 | chunk riêng của từng model |
| Chọn model theo nhu cầu / catalog | 15 | không nêu model |
| Mơ hồ, thiếu model (đúng là phải hỏi lại) | 8 | |
| Không có trong tài liệu / ngoài phạm vi | 10 | đúng là phải nói không biết |
| Giá, tồn kho, yêu cầu gặp người (handoff) | 5 | |
| Chào hỏi, câu lạ, thử prompt injection | 5 | |
| **Tổng** | **120** | **dev 70 / test 50**, phân tầng đều theo nhóm |

- **Nguồn:** 40% từ nhân viên QS (kinh doanh/hỗ trợ) viết mới, không xem tài liệu và không biết hệ thống trả lời thế nào; 30% từ log thật (ẩn thông tin
  cá nhân, bỏ trùng); 30% từ bộ YAML hiện có (đã duyệt). Mỗi câu ghi trường `source` (`staff`/`real`/`legacy`) để báo cáo điểm riêng theo nguồn.
- **Nhãn mỗi câu:** model, intent, route mong đợi, domain, chunk đúng (`expected`/`acceptable` theo `content_hash` + `section_path`), 1–4 **fact vàng**
  (câu ngắn kiểm được, ví dụ "kích thước 220×140×30 mm"), loại câu, `split`, `source`.
- **Chất lượng nhãn:** hai người gắn nhãn độc lập 30% số câu; độ đồng thuận (Cohen's kappa) ≥ 0,7 trước khi dùng; bất đồng thì Toma quyết và ghi lý do.
- **Biến thể (perturbation):** mỗi câu `test` sinh thêm 4 dạng (bỏ dấu; sai chính tả/viết tắt; thêm lời dẫn "cho mình hỏi…"; đảo trật tự/lẫn Việt–Anh)
  → 200 lượt đo phụ. Nhãn đúng giữ nguyên (`perturb_of` trỏ về câu gốc).
- **Công sức ước lượng:** viết + gắn nhãn 120 câu khoảng 10–14 giờ người, kiểm chéo thêm ~3 giờ.

### 8.3 Các giai đoạn

| GĐ | Việc | Đầu ra | Cổng quyết định |
|---|---|---|---|
| 0 | Công cụ: script xuất log ẩn danh; mở rộng schema YAML (`source`, `facts`, `perturb_of`); thêm vào `run_retrieval_eval.py`: context precision, số chunk nhiễu, `audience` theo kênh, ghi số biến thể đã thử; lưu `chunk_id` vào snapshot | công cụ + test | — |
| 1 | Xây bộ vàng 8.2; chấm nhãn 58 lượt đã lưu chunk để có precision sớm | file YAML + kappa | Toma duyệt nhãn |
| 2 | Baseline hiện trạng, không đổi gì: `--repeat 3`, model production `gpt-4o-mini`, `r0`, mọi chỉ số mục 4 có khoảng tin cậy, theo nhóm câu và theo `source` | báo cáo baseline | Chốt ngưỡng chấp nhận (mục 6) |
| 3 | Quét tham số chỉ trên `dev` (8.4) | bảng biến thể | chọn tối đa 3 ứng viên |
| 4 | Phân tích: `r0` vs `r1`/`r2` cùng model; 2–3 model ứng viên (D) | bảng so sánh | Toma chọn luật/model |
| 5 | Xác nhận 1 lần trên `test` + biến thể; end-to-end có chấm câu trả lời (8.5) | báo cáo xác nhận | đạt cổng 8.6 thì đổi mặc định |
| 6 | Giám sát hằng tuần + luân phiên bộ test hằng tháng (8.6) | báo cáo tuần | hồi quy thì dừng thay đổi |

### 8.4 Quét tham số (GĐ 3)

- **Cách quét:** từng tham số một quanh mặc định, rồi chỉ phối hợp 3–5 giá trị tốt nhất; không quét lưới toàn bộ (tránh chọn theo may rủi).
  Lưới: `min_similarity` {0,25; 0,35; 0,45; 0,50}, `final_chunk_top_k` {3, 4, 5, 6, 8}, `vector_k` = `fts_k` {10, 20, 40}, `rrf_k` {20, 60},
  `spec_boost` {0; 0,005; 0,01}, `target_boost` {0; 0,003; 0,005}. Thử riêng: cắt theo khoảng cách điểm; rerank.
- **Tiêu chí chọn (theo thứ tự):** (1) Recall@6 và `ngu_canh` không giảm quá biên nhiễu; (2) context precision tăng; (3) số chunk/token giảm; (4) độ trễ.
  Một biến thể chỉ được chọn khi cải thiện nằm ngoài khoảng tin cậy ghép cặp.
- **Chỉ chạy trên `dev`.** Tối đa 3 ứng viên được đưa sang `test`, mỗi cái chạy 1 lần; ghi số biến thể đã thử vào báo cáo (càng thử nhiều, kết quả tốt nhất
  càng có khả năng là may mắn).

### 8.5 Chấm câu trả lời

- Rubric mỗi câu 0–2: faithfulness (mọi khẳng định có trong chunk), correctness (khớp fact vàng), completeness, trích dẫn `[S#]` đúng chunk, nói "không biết" đúng lúc,
  hỏi lại đúng lúc, định dạng.
- **LLM-judge** dùng model khác với model sinh, temperature 0, chấm từng fact vàng có/không trong câu trả lời và từng khẳng định có chunk chống lưng không.
- **Hiệu chuẩn judge:** người chấm 30 câu; độ đồng thuận judge–người ≥ 0,8 mới dùng judge cho phần còn lại; không đạt thì chỉnh rubric/prompt judge. Người vẫn
  chấm mẫu 30% mỗi lần chạy chính.

### 8.6 Cổng chống overfit (trước khi đổi bất kỳ mặc định nào)

1. Chênh lệch `dev` − `test` ≤ 5 điểm % ở các chỉ số chính.
2. Điểm trên câu biến thể (bỏ dấu, sai chính tả…) thấp hơn câu gốc không quá 8 điểm %.
3. Điểm theo từng nhóm câu và theo `source`: không nhóm nào/nguồn nào tụt dưới ngưỡng chấp nhận (không chỉ trung bình).
4. Câu `source=staff` (độc lập với người chỉnh) không kém câu `legacy` quá 8 điểm %.
5. Cải thiện nằm ngoài khoảng tin cậy ghép cặp và biên nhiễu `--repeat`.
6. `test` chưa từng được dùng để chỉnh; mỗi biến thể chạy tối đa 1 lần.
7. **Luân phiên hằng tháng:** thêm 20–30 câu mới từ log thật vào `test`, chuyển 20–30 câu `test` cũ sang `dev`; nếu điểm trên câu mới tụt so với câu cũ ≥ 8
   điểm % thì bộ cũ đã bị "học thuộc".
8. **Đối chiếu trực tuyến:** sau khi chạy thật, so tỉ lệ hỏi lại, no_hits, lỗi, handoff và phản hồi khách với số đo ngoại tuyến; lệch có hệ thống nghĩa là bộ mẫu chưa đại diện.

## 9. Kế hoạch hiện hành (bản tối thiểu, không dùng LLM-judge)

Thay cho mục 8.2–8.6 khi hai bản khác nhau. Lựa chọn của Toma: cắt giảm tối đa, **không** dùng LLM-judge, có tầng kiểm thử sinh câu trả lời. Chưa duyệt
chính thức; mọi con số là ước lượng thô (±50%).

**Chi phí:** API ~1 USD (dự phòng 2); kỹ sư ~7–8 ngày công; người am hiểu sản phẩm ~19–29 giờ (tối đa ~40 nếu kiểm tự động không giảm được khối lượng chấm
tay); máy < 1 giờ. Lịch: 2–3 tuần toàn thời gian, 3–4 tuần bán thời gian.

**Hạn chế đã chấp nhận:** khoảng tin cậy rộng (test 25 câu ≈ ±16 điểm %) nên bộ này chẩn đoán lỗi và phát hiện chênh lệch lớn, không dùng để tinh chỉnh
ngưỡng từng bước nhỏ; mỗi lần đổi prompt/model phải chấm lại tay; không có luân phiên bộ test hằng tháng; không so nhiều model.

### 9.1 Giai đoạn

| GĐ | Việc | Ai | Đầu ra |
|---|---|---|---|
| 0 (~3 ngày công) | Script xuất log website ẩn danh (bỏ trùng, che email/số điện thoại/tên); mở rộng YAML (`source`, `facts`, `perturb_of`, loại câu); `run_retrieval_eval.py`: context precision, số chunk nhiễu, lọc `audience=public`, ghi số biến thể đã thử, lưu `chunk_id`; chế độ **oracle** (sinh câu trả lời từ chunk đúng) và **real** (ngữ cảnh thật); kiểm tự động (khớp fact vàng bằng chuỗi/regex, số và mã trong câu có nằm trong chunk được trích không, `[S#]` hợp lệ, phát hiện "không biết" bằng từ khóa); xuất/nhập bảng chấm CSV | kỹ sư | công cụ + test |
| 1 (QS 8–10 giờ) | Viết và gắn nhãn bộ vàng 9.2 và bộ bẫy 9.3; hai người gắn nhãn độc lập 12 câu, bất đồng thì Toma quyết | QS + Toma | `gold_v1.yaml`, `gen_traps.yaml` |
| 2 | **Baseline** chỉ trên `dev` (test đóng băng): tra cứu + phân tích `--repeat 2`, sinh oracle và real, kiểm tự động; người chấm 85 lượt (35 oracle + 35 real + 15 bẫy) theo từng khẳng định, gắn loại lỗi (bảng phân loại lỗi: bịa, trích sai chỗ, nhầm model/cột, nhầm số/đơn vị, thiếu, thừa, không nói "không biết") | kỹ sư chạy, QS chấm 7–11 giờ | báo cáo baseline có khoảng tin cậy (bootstrap) theo nhóm câu |
| 3 | **Chẩn đoán và chọn một thay đổi**: từ bảng lỗi quyết định hướng (tra cứu: `min_similarity` {0,25; 0,35; 0,45}, `top_k` {4,5,6} — phát lại, không tốn LLM; định dạng chunk bảng; prompt trả lời `v2`). Tối đa 3 ứng viên chạy trên dev | kỹ sư + Toma | 1 ứng viên |
| 4 | Điều kiện 2 trên `dev`: người chấm lại 50 lượt (35 real + 15 bẫy) | QS 4–7 giờ | so ghép cặp với baseline |
| 5 | **Xác nhận một lần** trên `test` (25 câu): baseline và ứng viên; chấm tay 50 lượt (oracle + real); 50 lượt biến thể (bỏ dấu, sai chính tả) chỉ đo tự động | QS 4–7 giờ | báo cáo xác nhận |
| 6 | Toma quyết đổi mặc định; viết lại `STATE.md`, thêm mục `LOG.md`. Giám sát sau đó chỉ tự động: tỉ lệ hỏi lại, no_hits, lỗi, cờ số/mã lạ mỗi tuần | Toma + kỹ sư | quyết định |

Người chấm chéo thêm 20% số lượt (3–5 giờ) để kiểm độ nhất quán giữa người chấm.

### 9.2 Bộ vàng 60 câu (dev 35 / test 25)

| Nhóm | Số câu |
|---|---|
| Thông số, kích thước | 10 |
| Đấu nối, lắp đặt | 10 |
| Cấu hình, vận hành | 8 |
| Chọn model theo nhu cầu / catalog | 7 |
| So sánh 2–3 model | 6 |
| Xử lý lỗi | 5 |
| Không có trong tài liệu / ngoài phạm vi | 5 |
| Mơ hồ, thiếu model | 4 |
| Giá, handoff | 3 |
| Chào hỏi, câu lạ, prompt injection | 2 |

Nguồn: 24 câu nhân viên QS viết mới (không xem tài liệu), 18 câu từ log thật đã ẩn danh, 18 câu từ bộ YAML hiện có; trường `source` để báo điểm riêng.
Nhãn mỗi câu: model, intent, route, domain, chunk đúng (`content_hash` + `section_path`), 1–4 fact vàng, loại câu, `split`, `source`.

### 9.3 Bộ bẫy cho bước sinh (15 câu)

So sánh nhiều model/cột 4; đọc bảng nhiều cột 4; chunk có thông số gần giống 3; không có đáp án trong chunk (kiểm abstention) 2; chunk mâu thuẫn/lệch nhau 2.

### 9.4 Chỉ số

- Tra cứu: Recall@1/3/5/6, MRR, `ngu_canh`, context precision, số chunk nhiễu mỗi lượt.
- Phân tích: intent, route, domain, F1 entities, độ ổn định qua 2 lần, lỗi phân tích.
- Sinh (tay + kiểm tự động): fact recall, đúng số và đơn vị, tỉ lệ khẳng định có chống lưng trong chunk, citation precision theo khẳng định, nhầm model/cột, bịa,
  thiếu, abstention đúng/nhầm; tách lỗi tra cứu và lỗi sinh bằng chế độ oracle.

### 9.5 Cổng trước khi đổi mặc định (đã hạ cho cỡ mẫu nhỏ)

1. Ứng viên so với baseline trên cùng câu `test`: ít nhất 5 câu chuyển từ sai sang đúng và không quá 1 câu chuyển ngược.
2. Chênh `dev` − `test` ≤ 10 điểm % (cảnh báo, không phải bằng chứng; n nhỏ).
3. Câu biến thể thấp hơn câu gốc không quá 10 điểm %.
4. Không nhóm câu nào về 0; nhóm `source=staff` không kém `legacy` quá 10 điểm %.
5. `test` chưa từng dùng để chỉnh; mỗi ứng viên chạy tối đa 1 lần; ghi số biến thể đã thử.

Ngưỡng chấp nhận ở mục 6 là mục tiêu dài hạn, chưa phải cổng của vòng này.

### 9.7 Trạng thái GD0 (2026-11-25): xong

Công cụ đã có và đã chạy thử (chi tiết: `docs/ai/flows/website-qa/LOG.md` cùng ngày): `evals/run_generation_eval.py`, `evals/gen_checks.py`, `evals/grading.py`,
`scripts/export_chat_log.py`, chỉ số `ctx_precision`/`nhieu` và trường câu mới trong `evals/run_retrieval_eval.py`, khung `evals/retrieval_cases/gold_v1.yaml`.

**Điều chỉnh kế hoạch do phát hiện ở GD0:** nhãn chunk của các bộ câu cũ đã lệch với `doc_chunks_v2` hiện tại (chunk `expected` còn khớp: `sample_f54_f86` 0/24,
`diverse_40` 3/84, `scope_f54` 0/23, `dual_source` 8/25, `catalog_f54_astro` 24/24). Vì vậy 18 câu "legacy" ở 9.2 không dùng được nguyên trạng: chỉ
`catalog_f54_astro` dùng ngay, các bộ khác phải gắn nhãn lại (cộng thêm công QS ở GD1, ước lượng +3–5 giờ), và số đo 14/11 không tái lập được để so sánh.

### 9.6 Cần Toma quyết trước khi bắt đầu

Duyệt cỡ và phân bổ bộ vàng; chỉ định người QS viết câu và chấm tay; kiểm số dư credit OpenAI (trace 2026-11-25 cho thấy `gpt-4o-mini` đang chạy); xác nhận
`gpt-4o-mini` vẫn là model sinh của website.
