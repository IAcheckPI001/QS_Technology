# Trạng thái luồng doc-ingest

Cập nhật: 2026-11-21

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- Hai đường tạo chunk nháp: PDF → S0/Docling → chuẩn hóa T-xx/V-01 → `build`; dữ liệu catalog biên soạn → `curated-build` (`source=manual`). Cả hai xuất `doc_chunks_v2.jsonl` + report; builder không ghi database. `chunking_loader` (ngoài `doc_ingest`) nạp run vào `doc_chunks_v2` (draft) là bước riêng; chat đọc `doc_chunks_v2` từ 2026-11-19.
- **crm-sync giai đoạn 1 (2026-11-19, nhánh `claude/crm-sync-phase1`, chưa merge):** `crm-plan` / `crm-fetch` / `crm-status` lấy PDF từ kho tài liệu công khai của CRM, so phiên bản với sổ nguồn `sources/crm/crm_sources.lock.json`, sinh manifest nháp có `source`. Đã chạy `run`/`build` 10 tài liệu bộ điều khiển tới bước sinh chunk, **dừng trước làm giàu**: 847 chunk nháp, **chưa duyệt, chưa nạp DB**. Chunk có `metadata.locations` (trang, vùng bbox) và `metadata.crm`.
- `quality-report` (2026-11-20, nhánh `claude/quality-report`, chưa merge): 739 chunk lá: 0 approved, **592 chặn chỉ vì OCR**, 61 chặn do lỗi, 86 chờ duyệt.
- **Kiểm duyệt 61 chunk lỗi bằng đối chiếu PDF (2026-11-20, [báo cáo](../../reports/p4_crm_chunk_review_2026-11-20.md)):** đề xuất 21 `can_sua`, 38 `ok_ghi_chu`, 2 `ok` (chưa ghi verdict). Gốc lỗi là luật pipeline (I-55…I-60), không phải chỉ OCR; V-01 bỏ sót các lỗi thật.
- **Bậc 0 (2026-11-20, chưa merge):** sửa I-55 (S0), I-59, I-54, I-56 nhẹ; chạy lại 10 tài liệu (`crm-1.1-t0`): 749 chunk lá, **54 chặn do lỗi (trước 61)**, 604 chỉ vì OCR, 91 chờ, 0 approved; trang V-01 chặn 17 → 1; 6AH có lại Step 1–2. 10iV chưa ép OCR tr.107–110 (cần parse lại, đang chạy).
- **Đối tượng xem (D-014, 2026-11-21, chưa merge):** manifest và chunk có `audience` (`public|internal`, mặc định `internal`; mọi manifest hiện có là `public`); export có cột `audience`, file export cũ không nạp được. `publish-assets` đẩy ảnh lên bucket private `doc-assets` (chưa chạy thật); các manifest đã đổi `storage_bucket` nên run cũ phải build lại.
- Chưa có: trích fact, gán unit, CLI review, xuất bản theo sổ nguồn, gỡ phiên bản cũ. Làm giàu VI có CLI và cổng 2c, F54 v4 chưa qua duyệt.

## Độ chín từng bước

| Bước | Luật | Trạng thái | Backlog |
|---|---|---|---|
| Nguồn CRM (plan, fetch, status) | — | có (giai đoạn 1); chưa nạp DB, chưa chạy theo lịch | — |
| Thống kê chất lượng chunk | — | có (`quality-report`, chỉ đọc); chưa có hạng rủi ro, chưa chọn mẫu duyệt | — |
| S0 + OCR theo trang, parse Docling | — | có; OCR chỉ tiếng Anh (I-29); chưa kiểm toàn vẹn text layer (I-55) | BL-24 |
| Khung chữ, header/footer, nhãn, mục lục | T-20, T-17, T-18, T-16 | có; ảnh nuốt chữ thủ tục (I-59) | BL-07, BL-10, BL-33 |
| Bảng logic; mã parameter, điều kiện áp dụng | T-01…T-05, T-15; T-12, T-13 | có; sai ranh giới hàng ô nhiều dòng, mất hàng (I-56) | BL-05, BL-06, BL-11, BL-27 |
| Trang in, section path, list cha–con | T-06, T-07, T-08 | có (list v1 mới kiểm trên F54) | BL-07…BL-09 |
| Hình: screenshot, watermark, trùng, caption, crop | T-09…T-11, T-14, T-19 | có; chưa nhận ảnh màn hình (I-57); chunk hình gộp trang (I-60) | BL-10 |
| Kiểm bất biến | V-01…V-04 | một phần: chỉ V-01, nhiều báo động giả, bỏ sót lỗi thật (I-54) | BL-25 |
| Chunk builder + kiểm 2b | C2 | có; thêm `locations`, `source_ref` (2026-11-19) | BL-15, BL-16 |
| Làm giàu tiếng Việt (Bước 3) | C2 §8, 2c | có trong code; F54 v4 chưa đạt 2c | — |
| Trích fact; duyệt theo unit | — | chưa có; một phần (lõi approval) | BL-17…BL-21 |
| Xuất bản → `doc_chunks_v2` | — | loader nạp draft được; chưa nạp theo sổ nguồn CRM | BL-22, BL-90… |

## Đang làm

Chờ Toma duyệt thứ tự sửa luật I-55 → I-59 → I-54 → I-57 → I-58 → I-56 → I-60 và quyết cơ chế I-53; xem verdict đề xuất
(`data/ingest_runs/_summary/chunk_review_proposed.csv`, trong worktree) rồi ghi `chunk_review.json`. Cổng 2c v4 không đạt (chờ prompt v5).

## Vấn đề mở

| ID | Mức | Vấn đề |
|---|---|---|
| I-53 | P0 | Không có cơ chế gỡ mã chặn: chunk có `review_blockers` luôn `draft` (`export/doc_chunks_v2.review_status`), dù S0 ghi "chặn cho tới khi người duyệt xác nhận" → chunk OCR không thể `approved`; đề xuất xác nhận theo trang trong manifest, chỉ cho `ocr_required` |
| I-55 | P0 | Text layer PDF 10iV tr.107–110 mất chữ số 0,1,2,4,5,6,8 và chữ `m` (`#8090` → `# 9`); V-01 mù. Ép OCR tr.107–110 khôi phục 223/223 mã đủ chữ số (so 2/137): thêm kiểm toàn vẹn text layer ở S0 |
| I-56 | P0 | Bảng cổng Installation: chân/dòng ô nhiều dòng gán sang hàng kề (`X57`, `X47`, `Y40`), hàng ANT mất (6AVE), CN7+8+9 gộp; 6 chunk `can_sua` |
| I-57 | P1 | Ảnh chụp màn hình và sơ đồ dựng thành bảng (F54 Operation chương 3: 8 chunk; 6AVE `B0026`): mất dấu âm, header lẫn đồng hồ |
| I-58 | P1 | Chữ trong ảnh trên trang có text layer bị mất (phụ lục tham số tr.95–97…): thiếu tiêu đề mục + header cột; F86 `B0113` tách ô khóa `#10000 - #10049` |
| I-59 | P1 | `picture_swallows_text`: 6AH, 6AVE mất Step 1–2 thủ tục 3.8.1 (bị phân loại `figure_text`); có thể còn thủ tục khác |
| I-54 | P1 | V-01: 17 trang trượt đều do nhãn hình, mục lục chấm dẫn, chỉ số trên (`1 st`), ký tự U+FFFE; không bắt được lỗi thật (ANT, I-55, I-58). Chuẩn hoá token, tách ngưỡng lặp thành cảnh báo |
| I-51 | P0 | Bản Operation là ảnh scan (92–105/97–110 trang OCR); mẫu OCR 24 chunk: 46% lỗi nặng, phần lớn do I-58/I-59, không do OCR đọc sai chữ rõ; xin PDF text layer chỉ giúp 10iV (I-55), có thể F10T |
| I-28, I-29, I-60 | P0 | F10T: khung hai cột thành picture; OCR tiếng Anh trên tài liệu Việt (rớt dấu); chunk hình gộp nhiều trang (10iV `B0022` tr.25–33) |
| I-52 | P1 | "F54 - Operation Guide" trên CRM (106 trang) khác bản V.02 đã xử lý (171 trang); nhãn cũ `f54/eval-*` không chép sang được |
| I-47…I-50 | P0 | Brochure: lỗi bảng mã font, cặp tên–giá trị, bảng icon, `section_path` rỗng → nguồn `curated/`. "Catalogue sản phẩm" đã bị gỡ khỏi cây CRM |
| I-46, I-40, I-41, I-30, I-32… | P1–P2 | Scope `maintenance`; đoạn lặp, errata, số mục in sai; `M0100.txt`; bảng cổng F86 lệch ô; bảng vẽ dạng ảnh; mục lục F86 |

Mô tả đầy đủ: [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md); I-51…I-54: LOG 2026-11-19, 11-20; I-55…I-60: [báo cáo kiểm duyệt](../../reports/p4_crm_chunk_review_2026-11-20.md).

## Kết quả kiểm gần nhất

Run `crm-1.0-a` (2026-11-19, profile `qs_controller`, không enrich; cổng 2b chưa có nhãn → trống). Mọi run: CQ không lỗi, 0 lỗi xuất v2, độ phủ V-01 100% theo chunk.
Bảng theo tài liệu: `quality-report --crm --run-id crm-1.0-a`. Installation (4 bản, 92 chunk lá): 27 bị chặn (24 do lỗi, 3 chỉ vì trang bìa OCR), 65 chờ duyệt. Operation (6 bản, 647 chunk lá): 626 bị chặn (589 chỉ vì OCR, 37 do lỗi), 21 chờ duyệt.
Test (từ `backend/`): `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 404 passed, 1 failed có sẵn (CRLF CSV baseline trong worktree).

## Bước tiếp theo

1. Toma duyệt thứ tự sửa luật và cơ chế I-53; ghi verdict 61 chunk (đề xuất sẵn); xin CRM bản PDF text layer cho 10iV (và F10T) nếu muốn bỏ nhánh ép OCR.
2. Đã sửa I-55 (S0; chờ parse lại 10iV), I-59, I-54, I-56 nhẹ. Còn I-57, I-58, I-56 đầy đủ, I-60, CQ-14; sau mỗi bước chạy lại `quality-report` để so trước/sau.
3. Điền `exclude_pages` trong 10 manifest CRM; sửa I-29 (OCR tiếng Việt) trước khi dùng `f10t-operation-vi`.
4. Giai đoạn 2 crm-sync: nạp `doc_chunks_v2` theo sổ nguồn, gỡ bản cũ khi bản mới được duyệt, xoá 3 tài liệu thử, `crm-plan` theo lịch. Sau đó: làm giàu (2c), V-02…V-04, trích fact.
