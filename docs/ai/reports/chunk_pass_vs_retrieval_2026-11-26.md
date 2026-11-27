# Chunk "đạt" và hiệu quả tra cứu (2026-11-26)

> **Lưu ý:** các số đo (recall@5, số chunk dưới 80 ký tự, số lượt chat, số chunk theo verdict) là ảnh chụp ngày 2026-11-26 trên DB và code lúc đó (HEAD `85b5e7c` + thay đổi chưa commit). Chúng sẽ lệch khi nạp lại, đổi catalog hoặc sửa chunker; đo lại trước khi trích. Chỉ mục: [STATE.md](../flows/doc-ingest/STATE.md).

Báo cáo đánh giá, chỉ đọc: đối chiếu code `doc_ingest` (nhánh `feature/deploy_ai_service`, HEAD `85b5e7c`
+ thay đổi staged chưa commit), Supabase thật (`doc_chunks_v2`, `chat_traces`, `chat_sessions`,
`chat_history`) và các số đo đã ghi trong LOG của doc-ingest và website-qa. Không đổi code, không ghi DB.

## 1. Tiêu chí "chunk đạt" trong code hiện tại

Một chunk đi qua ba tầng. Tầng sau không thay tầng trước.

| Tầng | Ai kiểm | Tiêu chí | Nơi trong code |
|---|---|---|---|
| A. Cấu trúc (tự động) | chunk builder | CQ-01…CQ-12 đạt: header bảng khớp cột, không cắt giữa dòng bảng, `content` ≤ ngân sách và bảng lặp header, provenance (doc, trang, `element_ids`), asset resolve được, `not_available` giữ nguyên văn, cha–con một cấp và con ⊂ cha, không tách định nghĩa parameter khỏi giá trị / caption khỏi hình, bảng nằm trọn trong `embed_text`, lá nằm trong ngân sách embed; độ phủ phần tử = 1,0 và 0 lặp | `build/assertions.py`, `build/quality.py::gate` |
| A'. Không có mã chặn | S0, chuẩn hoá T-xx, V-01 | `review_blockers` rỗng (vd. `ocr_required`, `heading_garbled`, `text_patch_unmatched`, bảng mồ côi) | `normalize/recorder.py`, `export/doc_chunks_v2.py::review_status` |
| B. Nội dung (duyệt) | người hoặc model đối chiếu ảnh trang | verdict `ok` cho đúng `content_hash`: chữ trong chunk khớp 100% phần PDF có dạng chữ; sơ đồ mà chi tiết chỉ nằm trong ảnh vẫn `ok` kèm `[image_only_info]` (chính sách GĐ0, Toma 2026-11-25) | `chunk_review.json`, `build/quality.py::review_summary` |
| C. Phát hành `approved` | export | (1) không mã chặn, (2) verdict `ok` đúng hash, (3) cổng 2b đạt **không tạm**: ranh giới precision và recall ≥ 0,9 trên nhãn đã xác nhận, 0 `fix` mở trong tài liệu, (4) chunk lá: làm giàu đã duyệt ở cổng 2c. Chunk `manual` (catalog): nguồn biên soạn đã duyệt hết (`curated_verified`) + verdict `ok` | `export/doc_chunks_v2.py::review_status` |

Không tầng nào hỏi "câu hỏi thật của khách có tìm ra chunk này không". Tầng A–C đo **độ trung thực**
(chunk nói đúng điều PDF nói, đủ provenance) và **độ toàn vẹn cấu trúc**, không đo **khả năng được tìm thấy**
hay **đủ thông tin để trả lời**.

## 2. Hiện trạng trên Supabase (2026-11-26, chỉ đọc)

- `doc_chunks_v2`: 1.057 dòng, 983 active, **0 `approved`**. 911 chunk CRM của 10 tài liệu (run
  `crm-1.2-a`, `crm-1.4-a`, `crm-1.6-a`, `crm-1.6-b`) + 72 chunk catalog (`curated-b2`, active); 37 + 37 dòng
  catalog inactive (`curated-a` A, `curated-b3` B, dùng cho thí nghiệm). 23 dòng `f86_installation_2024-04-25`
  mà STATE cũ nhắc **không còn** trong bảng.
- 808/983 dòng active có `metadata.review_blockers` → kể cả khi verdict `ok`, các chunk này vẫn `draft` (I-53).
- Chunk lá CRM: 786; **130 chunk (16,5%) dưới 80 ký tự, 383 (49%) dưới 200 ký tự**. Bản Installation nặng
  nhất: F54 13/17, 6AVE 18/35, F10T 13/30, F86 12/23 chunk lá dưới 80 ký tự (phần lớn là tiêu đề hình có ảnh).
- Verdict theo run đã nạp (trong `chunk_review.json`, không nằm trên DB): 911 chunk = 596 `ok`, 307 `fix`,
  8 `pending`. Run `crm-1.7-a` (S0 trang lai + T-22) có 623 `ok` / 291 `fix` nhưng **chưa nạp** và code chưa commit.
- Lượt chat từ lúc nạp lại (2026-11-25 10:00 UTC): 14 trace website (9 có tra cứu, 4 không áp dụng, 1
  `analysis_error`); tài liệu được trả về chỉ gồm `qs_product_catalogue`, `f54-installation-en`,
  `f54-operation-en`; `best_similarity` 0,61–0,72. Kênh CRM không có lượt mới. Trace ghi `doc_ids` và điểm cao
  nhất, không ghi chunk nào đúng → **không đo được hiệu quả tra cứu từ log thật**, chỉ từ bộ câu có nhãn.

## 3. Chunk đạt có đồng nghĩa tra cứu hiệu quả? — Không

Chunk đạt là **điều kiện cần cho câu trả lời đúng**, không phải **điều kiện đủ cho tra cứu tốt**.

Bằng chứng chiều "cần" (chunk hỏng thì tra cứu hỏng chắc chắn):
- `10iv-operation-en` mất chữ số (I-55): `# - # 7` thay cho `#0000 - #0007` → G118 không thể trả lời đúng.
- `f10t-operation-vi` rớt dấu (I-29, ≥ 49/147 chunk): G116 không có chunk đúng ở top.

Bằng chứng chiều "không đủ" (chunk đạt mà vẫn tìm kém):
1. **Cùng nội dung trung thực, cách chia khác → kết quả khác hẳn.** Catalog A (37 chunk) và C (72 chunk) đều
   qua `curate-check`, chữ bám PDF. Trên cùng bộ nhãn: core r@1 A 0,60, C0 0,25, C1 0,60; K16 (liệt kê
   Mechatrolink) hạng 2 → 6, K06 (so sánh) 6 → 10, trong khi K10, K19 lên hạng 1 (LOG doc-ingest 2026-11-25).
2. **Chunk `ok` nhưng không có gì để tìm/trả lời.** Chính sách `[image_only_info]` cho phép chunk chỉ có tiêu
   đề hình là `ok`. 130 chunk lá < 80 ký tự; H13 (chunk "2.8 POWER CONNECTION" chỉ có tiêu đề) khiến câu trả
   lời bịa "24V [S1]"; cổng 2c v5 F86 không đạt vì 13/23 chunk chỉ có tiêu đề hình.
3. **Chunk anh em chồng lấn.** Trên catalog, chunk đúng không ở hạng 1 chủ yếu vì chunk cùng model gần trùng
   và bảng nhiều model; vector-only đã đạt R@6 0,96 → hàm tìm không phải điểm nghẽn (LOG website-qa 2026-11-25).
4. **Lỗi ngoài chunk.** Định tuyến (`lookup.product_info` chỉ tìm catalog: G114; tên `10i` lệch `10iV` của kho:
   G108, G118 → `no_docs`; hãng INVT bị coi là model: G113); `min_similarity` không tách được đúng/sai (trung vị
   chunk đúng 0,545 so với chunk sai cao nhất 0,579); câu quy trình dài xếp rất thấp (G107 hạng 29).
5. **Kết quả đo tài liệu kỹ thuật kém hơn catalog rõ rệt**: bộ vàng nháp 12 câu dev, web1 recall@5 0,42,
   ctx_precision 0,13 (catalog recall@5 ≈ 1,0). Một phần do chunk hỏng (chiều "cần"), một phần do 1–4.

## 4. Đề xuất (chờ Toma quyết, chưa làm)

1. Thêm tầng **D. "tìm được"** theo tài liệu, trước khi mở `approved`: mỗi tài liệu có 5–10 câu vàng (QS duyệt,
   kèm fact là mã/số), đo bằng `run_retrieval_eval.py` trên DB dev; ngưỡng (vd. recall@5, tỉ lệ fact có trong
   ngữ cảnh) do Toma chốt. Tầng D là cổng của **tài liệu/phiên bản chia chunk**, không phải của từng chunk.
2. Kiểm tự động mới ở mức chunk (cảnh báo, không chặn): chunk lá chỉ có tiêu đề (< N ký tự, không bảng) →
   gộp vào mục cha hoặc đánh dấu không embed; `product_models` khớp registry (10i/10iV); cặp chunk anh em gần
   trùng (cosine `embed_text` cao).
3. Trace ghi id chunk được đưa vào ngữ cảnh (`retrieved_chunk_ids` hiện chưa điền) để đối chiếu lượt thật với
   verdict chunk.
4. Thứ tự đề xuất: commit/nạp `crm-1.7-a` (sau khi Toma duyệt S0 trang lai + T-22) → xử lý chunk chỉ-tiêu-đề →
   bộ vàng theo tài liệu → I-53 và `approved`.
