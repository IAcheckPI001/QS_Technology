# Trạng thái luồng doc-ingest

Cập nhật: 2026-11-19

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- Hai đường tạo chunk nháp: PDF → S0/Docling → chuẩn hóa T-xx/V-01 → `build`; dữ liệu catalog biên soạn → `curated-build` (`source=manual`). Cả hai xuất `doc_chunks_v2.jsonl` + report; builder không ghi database. `chunking_loader` (ngoài `doc_ingest`) nạp run vào `doc_chunks_v2` (draft) là bước riêng; chat đọc `doc_chunks_v2` từ 2026-11-19.
- **crm-sync giai đoạn 1 (2026-11-19, nhánh `claude/crm-sync-phase1`, chưa merge):** `crm-plan` / `crm-fetch` / `crm-status` lấy PDF từ kho tài liệu công khai của CRM, so phiên bản với sổ nguồn `sources/crm/crm_sources.lock.json`, sinh manifest nháp có `source`. Đã tải 11 tài liệu (10 bộ điều khiển + Hồ sơ công ty) và chạy `run`/`build` tới bước sinh chunk, **dừng trước làm giàu**: 847 chunk nháp, **chưa duyệt, chưa nạp DB**.
- Chunk có vị trí trong PDF: `metadata.locations` (trang + vùng bbox + kích thước trang) và `metadata.crm` (id, mã file, version; không lưu URL đã ký).
- Chưa có: trích fact, gán unit, CLI review, xuất bản theo sổ nguồn, gỡ phiên bản cũ. Làm giàu VI có CLI và cổng 2c, F54 v4 chưa qua duyệt.

## Độ chín từng bước

| Bước | Luật | Trạng thái | Backlog |
|---|---|---|---|
| Nguồn CRM (plan, fetch, status) | — | có (giai đoạn 1); chưa nạp DB, chưa chạy theo lịch | — |
| S0 + OCR theo trang, parse Docling | — | có; OCR chỉ tiếng Anh (I-29) | BL-24 |
| Khung chữ, header/footer, nhãn, mục lục | T-20, T-17, T-18, T-16 | có | BL-07, BL-10, BL-33 |
| Bảng logic; mã parameter, điều kiện áp dụng | T-01…T-05, T-15; T-12, T-13 | có | BL-05, BL-06, BL-11, BL-27 |
| Trang in, section path, list cha–con | T-06, T-07, T-08 | có (list v1 mới kiểm trên F54) | BL-07…BL-09 |
| Hình: screenshot, watermark, trùng, caption, crop | T-09…T-11, T-14, T-19 | có (chưa render trang xoay) | BL-10 |
| Kiểm bất biến | V-01…V-04 | một phần: chỉ V-01 | BL-25 |
| Chunk builder + kiểm 2b | C2 | có; thêm `locations`, `source_ref` (2026-11-19) | BL-15, BL-16 |
| Làm giàu tiếng Việt (Bước 3) | C2 §8, 2c | có trong code; F54 v4 chưa đạt 2c | — |
| Trích fact; duyệt theo unit | — | chưa có; một phần (lõi approval) | BL-17…BL-21 |
| Xuất bản → `doc_chunks_v2` | — | loader nạp draft được; chưa nạp theo sổ nguồn CRM | BL-22, BL-90… |

## Đang làm

Duyệt nội dung trích xuất của 10 tài liệu CRM (`data/ingest_runs/<doc_id>/crm-1.0-a/report/chunks.html`, trong
worktree của nhánh), Installation trước. Cổng 2c v4 không đạt (chờ prompt v5); catalog `curated-a` chờ verdict.

## Vấn đề mở

| ID | Mức | Vấn đề |
|---|---|---|
| I-51 | P0 | Bản Operation trên CRM (10iV, 6AH, 6AVE, F10T, F54, F86) là ảnh scan: 92–105/97–110 trang OCR; 606/847 chunk bị chặn `ocr_required` → cần kiểm OCR trước khi duyệt |
| I-28, I-29 | P0 | F10T: khung hai cột thành picture; OCR tiếng Anh trên tài liệu tiếng Việt (`f10t-operation-vi`: `ocr_lang_mismatch`, 1.370 ký tự VI) |
| I-52 | P1 | "F54 - Operation Guide" trên CRM (106 trang) khác bản V.02 đã xử lý (171 trang, sha khác); duyệt/nhãn cũ `f54/eval-*` không chép sang được |
| I-47…I-50 | P0 | Brochure (catalog, hồ sơ công ty): lỗi bảng mã font, cặp tên–giá trị, bảng icon, `section_path` rỗng → nguồn `curated/`. "Catalogue sản phẩm" đã bị gỡ khỏi cây CRM (2026-11-19) |
| I-46 | P1 | Scope theo nội dung: còn siết luật `maintenance` |
| I-40 (c,d), I-41, I-30 | P2 | Đoạn lặp; errata; số mục in sai; `M0100.txt` nhận nhầm là parameter |
| I-32, I-22, I-31, I-33…I-35 | — | Bảng cổng F86 lệch ô; bảng vẽ dạng ảnh; mục lục F86; hình không caption; độ hạt bảng cổng; luật loại chunk |

Mô tả đầy đủ: [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md); I-51, I-52: LOG 2026-11-19.

## Kết quả kiểm gần nhất

Run `crm-1.0-a` (2026-11-19, profile `qs_controller`, không enrich, không figure-ocr; cổng 2b chưa có nhãn → trống):

| Tài liệu | Trang (OCR) | Chunk (cha/con/độc lập) | Độ phủ | Chặn `ocr_required` | Ghi chú |
|---|---|---|---|---|---|
| f54-installation-en | 19 (1) | 17 (0/0/17) | 77/77 | 1 | |
| f86-installation-en | 26 (1) | 22 (0/0/22) | 53/53 | 1 | trùng file `f86_italliation` cũ |
| f10t-installation-vi | 27 (1) | 23 (0/0/23) | 62/62 | 1 | 5 `column_count_mismatch` |
| 6ave-installation-vi | 32 (1) | 30 (0/0/30) | 84/84 | 1 | 6 `column_count_mismatch` |
| f86-operation-en | 97 (92) | 115 (15/31/69) | 679/679 | 92 | trùng file `f86` cũ |
| 6ah-operation-en | 103 (98) | 125 (18/37/70) | 783/783 | 99 | |
| f10t-operation-vi | 105 (101) | 128 (19/43/66) | 601/601 | 102 | OCR sai ngôn ngữ |
| f54-operation-en | 106 (100) | 144 (18/40/86) | 737/737 | 118 | |
| 10iv-operation-en | 110 (97) | 115 (18/37/60) | 595/595 | 91 | |
| 6ave-operation-en | 110 (105) | 128 (20/41/67) | 644/644 | 100 | |
| qs-company-profile | 24 (0) | — (`run --no-build`) | — | — | trùng file `qs_company` cũ |

Mọi run: CQ không lỗi, 0 lỗi xuất v2, mọi chunk có `locations` + kích thước trang + `metadata.crm`.
Test (từ `backend/`): `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 396 passed, 1 failed có sẵn (CRLF CSV baseline trong worktree).

## Bước tiếp theo

1. Toma duyệt `chunks.html` 4 bản Installation, rồi các bản Operation (kiểm OCR); quyết hướng I-51 (OCR chất lượng cao hơn / bản PDF có text layer từ CRM).
2. Sửa I-29 (OCR tiếng Việt) trước khi dùng `f10t-operation-vi`; điền `exclude_pages` trong 10 manifest CRM.
3. Giai đoạn 2 crm-sync: nạp `doc_chunks_v2` theo sổ nguồn, gỡ phiên bản cũ khi bản mới được duyệt, xoá 3 tài liệu thử; chạy `crm-plan` theo lịch.
4. Sau đó: làm giàu (2c, prompt v5), V-02…V-04, trích fact, gán unit và CLI review.
