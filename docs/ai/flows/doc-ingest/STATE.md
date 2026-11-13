# Trạng thái luồng doc-ingest

Cập nhật: 2026-11-14

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- Pipeline chạy từ PDF tới chunk nháp: S0 → Docling → chuẩn hóa (T-xx) → V-01 → `build`.
- **Chưa ghi database.** Bảng `doc_chunks` vẫn chứa chunk F86 biên soạn tay.
- Chưa có: đánh giá tra cứu offline, trích fact, gán unit, CLI review, xuất bản. Làm giàu VI: thí điểm 20 chunk.
- F54 (`eval-k`): 296 chunk, **cổng 2b đạt (tạm)** 296 ok / 0 fix (nhãn `verified: false`); 2c tự động đạt, 30 mẫu chờ.
- D-008: tra cứu chỉ tìm trên chunk con/độc lập, cha chỉ mở rộng ngữ cảnh; phía SQL/retriever chưa làm.
- F86 Installation, F86 Operation chưa được team duyệt; F10T, F86 Operation không đạt cổng đánh giá (OCR).

## Độ chín từng bước

| Bước | Luật | Trạng thái | Backlog |
|---|---|---|---|
| S0 hồ sơ tài liệu + OCR theo trang | — | có | BL-24 |
| Parse Docling | — | có | — |
| Khung chữ, nhãn khung | T-20 | có (chỉ trang text layer) | — |
| Header/footer, nhãn sát hình | T-17, T-18 | có | BL-07, BL-10 |
| Phân loại nhãn, mục lục | T-16 | có | BL-33 |
| Bảng logic | T-01…T-05, T-15 | có | BL-05, BL-06, BL-27 |
| Mã parameter, điều kiện áp dụng | T-12, T-13 | có (ô bảng + text) | BL-11 |
| Trang in, section path | T-06, T-07 | có (dời hình lạc thứ tự; chưa có ghi đè manifest) | BL-07, BL-08 |
| List cha–con | T-08 | có (v1, mới kiểm trên F54) | BL-09 |
| Hình: screenshot, watermark, trùng, caption, crop | T-09, T-10, T-19, T-11, T-14 | có (chưa render trang xoay) | BL-10 |
| Kiểm bất biến | V-01…V-04 | một phần: chỉ V-01 | BL-25 |
| Đánh giá đa tài liệu | — | có; nhãn mẫu `verified: false` | BL-34 |
| Chunk builder + kiểm 2b | C2 | có (CQ-01…CQ-12, R-12, R-13, loại theo manifest); F54 đạt cổng 2b (tạm) | BL-15, BL-16 |
| Làm giàu tiếng Việt (Bước 3) | C2 §8, 2c | có (`cli enrich`, prompt v4 + thuật ngữ; cổng 2c); F54 243/243 lá, 30 mẫu chờ duyệt | — |
| Trích fact | — | chưa có | BL-17 |
| Duyệt theo unit | — | một phần: lõi approval; chưa gán unit, chưa CLI | BL-18…BL-21 |
| Xuất bản → `doc_chunks` | — | chưa có; loader phải bỏ qua embed cha (D-008) | BL-22, BL-90… |

## Đang làm

Cổng 2c v4 **không đạt** (chờ prompt v5); vision (`vision-trial-3`, 14 chunk) chờ duyệt. Ảnh (chốt 2026-11-14):
`embed_text` chỉ câu mô tả có mã phân biệt; bỏ fact dịch nhãn; fact có quan hệ ngoài embed. Build/`enrich`: venv chính.

## Vấn đề mở

| ID | Mức | Vấn đề |
|---|---|---|
| D-008 (tra cứu) | — | Cột `chunk_role` + lọc cha trong `match_doc_chunks` chưa làm (cùng bước xuất bản, E-01) |
| I-40 (c), (d) | P2 | Đoạn lặp nguyên văn ở nhiều mục; lỗi in của PDF gốc (cần errata cấp manifest) |
| I-46 | P1 | Scope theo nội dung (`eval-m`, đã nạp, đo **đạt**; CP-I46 để khôi phục). Còn: siết luật `maintenance` (B0175 M100 bị gán bảo trì) |
| I-41 | P2 | Số mục in sai (3.3.x) làm `section_path` của 3.3.4, 3.3.5, 3.9.2 và 4.3.6 thành mục gốc |
| I-32 | P0 (bảng cổng) | Bảng cổng F86 Installation lệch ô mô tả giữa các dòng |
| I-28, I-29 | P0 | F10T: khung trang hai cột bị nhận là picture; OCR tiếng Anh trên tài liệu tiếng Việt |
| I-30 | P1 | `M0100.txt` (tên macro) bị nhận là parameter |
| I-22, I-31, I-33…I-35 | — | Bảng vẽ dạng ảnh (F86 trang 15); mục lục F86 không nhận; chunk hình không caption; độ hạt bảng cổng; luật loại chunk thô |

Mô tả đầy đủ: [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md); I-46: website-qa LOG.

## Kết quả kiểm gần nhất

Chunk nháp, đọc từ `chunk_quality.json` và `chunk_review.json` ngày 2026-11-13:

| Tài liệu (run) | Chunk (cha/con/độc lập) | CQ, độ phủ, ranh giới | Duyệt tay ok / fix / chờ |
|---|---|---|---|
| F54 (`f54/eval-l` = `eval-k` + `doc_chunks_v2.jsonl`, 243 lá làm giàu v4) | 296 (53/150/93) | đạt; 1,0; P/R 1,0 | 296 / 0 / 0 |
| F86 Installation (`f86_italliation/eval-j-regress`, không render ảnh) | 23 (0/0/23) | đạt; 1,0; P/R 1,0 | 0 / 0 / 23 |
| F86 Operation (`f86/eval-b`, nháp) | 16 (0/0/16) | đạt; 1,0; — | 0 / 0 / 16 |

Mốc so sánh: `f54/eval-i` (301, thí điểm làm giàu), `f54/eval-h` (301, chưa làm giàu), `f54/eval-c` (342, 42 fix); lớp chuẩn hóa: [archive](LOG-archive-2026-11-09.md) mục 7.

Test (2026-11-13, từ `backend/`): `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 358 passed.

## Bước tiếp theo

1. Đã nạp `eval-l` (F54, F86) vào `doc_chunks_v2` (draft) → đo tra cứu web (bộ câu hỏi) → vision, prompt v5, 2c.
   → Bước 4 đánh giá tra cứu offline (gồm biến thể "không tìm cha", D-008) → Bước 5 schema `doc_chunks`.
2. Team xác nhận nhãn mẫu và nhãn ranh giới (`verified: true`), chạy lại `eval`; ghi
   `chunk_review.json` cho F86 Installation.
3. I-32 trước khi dùng chunk `pinout` của F86 Installation; quyết định hướng sửa I-28…I-30; I-41, I-40 (c, d).
4. Sau đó: V-02…V-04 (BL-25), trích fact (BL-17), gán unit và CLI review (BL-19, BL-21),
   xuất bản (BL-22, BL-90…, gồm D-008 phía SQL), chạy F86 đủ 97 trang (BL-13).
