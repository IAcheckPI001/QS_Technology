# Kế hoạch xử lý chunk `fix` và `pending` (2026-11-25)

Liên quan: [p4_crm_fix_recheck_result_2026-11-25.md](p4_crm_fix_recheck_result_2026-11-25.md), [p4_t15b_t04b_dryrun_2026-11-25.md](p4_t15b_t04b_dryrun_2026-11-25.md). Số liệu đo từ `chunk_review.json` mới nhất của 10 tài liệu CRM và `fix_recheck.csv` (372 chunk lá đã đối chiếu). Verdict trong file là của model, chưa người xác nhận từng chunk.

## 1. Hiện trạng

| | Số chunk |
|---|---|
| `fix` | 417 (lá 362: standalone 263 + con 99; cha 55) |
| `pending` | 22 trước đợt duyệt 7 chunk Installation; còn 15 chunk cha (`section`) |
| Lá `fix` đã phân loại nguyên nhân | 302 (F54/F86 Installation đã xử lý) |
| Lá `fix` chưa phân loại | 60 (F10T Operation chưa duyệt lại, giữ verdict cũ) |
| Bị chặn chỉ vì `ocr_required` | 384 / 432 |

Theo tài liệu (lá `fix`): F10T Operation 113, 10iV 46, 6AH 51, 6AVE Operation 49, F54 Operation 56, F86 Operation 27, 6AVE Installation 8, F10T Installation 11, F54 Installation 1.

## 2. Nguyên nhân và cách xử lý (302 lá đã phân loại)

Nguyên nhân chính (đứng đầu chuỗi nguyên nhân; một chunk có thể có nhiều nguyên nhân):

| Nguyên nhân | Chunk | Mức | Hành động đề xuất |
|---|---|---|---|
| I-58 chữ trong ảnh mất (sơ đồ chỉ còn caption) | 97 (106 kể cả phụ) | S2 101 / S1 5 | manual_curate 96 → **cần quyết chính sách** (mục 3) |
| I-59 ảnh nuốt chữ thủ tục (mất Step 1–2) | 58 | S2 | rule_fix 26, manual_curate 33 |
| I-51 bản scan/OCR (chữ vỡ, 0/O) | 43 | S1 29 | re_ocr 35 |
| I-29 OCR tiếng Anh trên tài liệu Việt | 32 | S3 28 | re_ocr 24 |
| I-56 ô gán sai hàng/cột | 30 | S1 19 | rule_fix 27 |
| I-57 ảnh màn hình thành bảng/chữ rời | 14 | S1 12 | drop 5, manual 6 |
| chunk_split (tách bảng/thủ tục) | 13 | S2 | merge 9, rule_fix 8 |
| I-60 chunk hình gộp nhiều trang | 7 (16 kể cả phụ) | S2 | manual 12, drop 3 |
| Mất ký tự trong bảng parameter (10iV) | 6 | S1 | re_ocr 8 |

Theo hành động (302): manual_curate 145, re_ocr 67, rule_fix 67, merge 14, drop_chunk 7, exclude_pages 2.

## 3. Quyết định chính sách cần làm trước (Giai đoạn 0)

1. **Chunk sơ đồ chỉ có caption (I-58, ~97 chunk).** Hai bản Installation đã duyệt `ok` kiểu chunk này (ảnh nằm trong asset, nội dung chân lấy từ bảng cổng), còn các bản Operation đang xếp `fix`. Hai chuẩn khác nhau. Đề xuất chuẩn chung: `ok` nếu chunk phản ánh đúng caption, giữ ảnh và thông tin chi tiết có ở nơi khác trong tài liệu (bảng cổng); `fix` nếu sơ đồ là nguồn duy nhất của thông tin. Áp chuẩn này có thể đóng phần lớn 97 chunk mà không sửa nội dung, nhưng chúng vẫn yếu khi tra cứu; đó là đối tượng của nghiên cứu làm giàu (mục 6).
2. **Cơ chế I-53 (gỡ `ocr_required`).** Điều kiện `approved` còn đòi cổng 2b và 2c; xem [LOG doc-ingest 2026-11-25](../flows/doc-ingest/LOG.md). Cần quyết sau khi nội dung ổn định.
3. **Ai biên soạn tay phần manual_curate** và dùng cơ chế nào: mở rộng lớp vá ô T-21 (chuỗi con trong ô bảng) hay chunk biên soạn riêng (`curated/`).
4. **Có xin CRM bản PDF có text layer** cho 10iV và F10T để bỏ nhánh OCR ép buộc không (giảm 67 chunk re_ocr).

## 3b. Kết quả Giai đoạn 0 (Toma chốt 2026-11-25)

1. **I-58:** chunk sơ đồ mà chi tiết chỉ nằm trong ảnh là `ok` kèm cờ `image_only_info` khi chữ trong chunk khớp 100% phần PDF có dạng chữ; mất chữ thật vẫn `fix`. Đã áp cho 64 chunk (6AVE Operation 19, F54 Operation 18, 10iV 13, 6AH 13, F86 Operation 1); 42 chunk còn lại của nhóm I-58 vẫn `fix` vì mất chữ hoặc OCR vỡ. Tổng sau áp: `ok` 522, `fix` 353, `pending` 15.
2. **Biên soạn tay:** mở rộng lớp vá ô T-21, thêm vá cho chunk (bổ sung văn bản). Ảnh lặp ở nhiều tài liệu (cảm biến 3/4/6 dây, CN2 tay quay) soạn một lần dùng chung.
3. **PDF nguồn:** không xin CRM bản text layer; tự OCR lại tiếng Việt cho F10T và OCR ép buộc cho 10iV tr.107–110 (cần đối chiếu từng chunk vì còn nguy cơ nhầm 0/O).
4. **I-53:** làm sau khi nội dung ổn định (sau Giai đoạn 1–5).

Lưu ý: cờ `image_only_info` hiện chỉ nằm trong ghi chú verdict, chưa có trong schema chunk/DB.

## 3c. Kết quả Giai đoạn 1 (2026-11-25)

Luật T-20b (khung "Memo" trên trang OCR) đã merge (`aba3a6d`). Dựng lại F86, F54, 6AH, 6AVE, 10iV Operation thành `crm-1.6-a`; 77 chunk lá đổi được đối chiếu ảnh trang: 67 `ok`, 10 `fix`. `fix` của 5 bản này giảm 201 → 155. Tổng 10 tài liệu: `ok` 596, `fix` 307, `pending` 8. Phần còn lại của I-59 là lỗi tiêu đề bị OCR hỏng (mục 3.4.2 gắn nhầm 3.4.1, mục 3.9.2 lẫn Note của 3.10), cần luật khôi phục tiêu đề; xem LOG doc-ingest cùng ngày.

## 4. Các giai đoạn

Thứ tự theo hiệu quả trên công sức; mỗi luật mới theo quy trình đã dùng cho T-15b: dry-run so với bản gốc, tiêu chí chấp nhận (chỉ đổi đúng tập chunk dự kiến, `tests\doc_ingest` qua, baseline F86 không đổi, bảo toàn chữ), run id mới, Toma duyệt.

| GĐ | Nội dung | Chunk dự kiến | Công sức |
|---|---|---|---|
| 0 | Quyết chính sách mục 3 | đóng tới ~97 (I-58) | thảo luận |
| 1 | Luật cho I-59 (ảnh nuốt chữ thủ tục): tìm vì sao Docling gộp chữ vào vùng ảnh (cả trang đầu của thủ tục); luật tách chữ ra khỏi ảnh | 58 (26 rule_fix) | trung bình–cao, cần khảo sát raw |
| 2 | I-56: mở rộng T-15b cho bảng Operation (23 `orphan_row`: 13 đầu bảng, 9 giữa trang), vá ô T-21 cho F10T/6AVE Installation (6AVE cần thao tác tách hàng) | 30 + 19 Installation | trung bình |
| 3 | chunk_split và gộp: nối chunk con thiếu bước, lặp tiêu đề cột, đúng ranh giới mục 4.2/4.3 | 13 + 14 merge | thấp–trung bình |
| 4 | re_ocr: F10T Operation ép OCR tiếng Việt (I-29), 10iV trang 107–110 ép OCR (I-55), hoặc xin PDF text layer | 67 | cần đo thời gian chạy; có thể vài chục phút mỗi tài liệu, chưa đo |
| 5 | manual_curate phần còn lại sau GĐ 0–4 và `drop_chunk` | ≤ 50 sau GĐ 0 (ước tính, chưa kiểm) | cao (người) |
| 6 | Dựng lại, carry verdict theo hash, duyệt lại chỉ chunk đổi, mẫu người xác nhận (ưu tiên 72 chunk S1), 15 chunk cha `pending` | — | trung bình |

Thứ tự theo tài liệu: bản Installation còn lại (F10T 11, 6AVE 8), sau đó F86 Operation (27, nhỏ nhất), F54 Operation, 6AH, 6AVE Operation, 10iV, cuối cùng F10T Operation (113 chunk, nhiều nhất và cần re_ocr).

## 5. Tiêu chí hoàn thành mỗi giai đoạn
- Số chunk `fix` của nhóm nguyên nhân giảm đúng dự kiến, không chunk `ok` nào đổi hash ngoài tập dự kiến.
- 0 `orphan_row`/`unassigned_cell` mới; CQ không lỗi; độ phủ 1,0.
- Test `tests\doc_ingest` qua; báo cáo kết quả ghi vào LOG và STATE.

## 6. Nghiên cứu làm giàu (sau khi xong GĐ 0)
Đối tượng: chunk chỉ có caption/ít chữ đã được chấp nhận `ok` theo chính sách GĐ 0. Kết quả thử 22 ảnh (2026-11-25): ảnh màn hình/thao tác làm giàu tốt, sơ đồ đấu dây và bản vẽ kích thước không đáng làm giàu bằng model (quan hệ chân sai 2/5, gán nghĩa số đo không ổn định). Chưa có số đo hiệu quả tra cứu. Bước tiếp: dựng 30 chunk màn hình + 30–50 câu hỏi thật do Toma duyệt, đo recall@5 cho ba cách nhúng. Chi phí ước tính 0,2–0,4 USD và khoảng nửa ngày công. Phụ thuộc: chunk đã ổn định (đổi hash làm mất bản làm giàu), và cơ chế I-53.
