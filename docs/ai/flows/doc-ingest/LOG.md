# Nhật ký luồng doc-ingest

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính. Sau khi thêm mục, viết lại [STATE.md](STATE.md).
Mẫu mục: [../_template/LOG.md](../_template/LOG.md).

Các mục tới 2026-11-09: [LOG-archive-2026-11-09.md](LOG-archive-2026-11-09.md).

## 2026-11-26 · Đối chiếu trạng thái (git + Supabase); chunk "đạt" chưa đồng nghĩa tra cứu tốt (I-61) · loại: đánh giá, kiểm chứng
- Vấn đề: STATE lệch thực tế (ghi "chưa push", DB 971 dòng, còn 23 dòng `f86_installation_2024-04-25`); cần trả lời tiêu chí chunk đạt và quan hệ với hiệu quả tra cứu.
- Kiểm chứng (chỉ đọc, không đổi code/DB): `git branch --contains` → T-15b `a0ce51a`, T-21 `c3b1177`, T-20b `aba3a6d` **đã có trên `origin/feature/deploy_ai_service`**; S0 trang lai, T-22, sửa asset lồng, catalog phương án C và `--no-slices` đang **staged, chưa commit**.
  Supabase: `doc_chunks_v2` 1.057 dòng, 983 active, 0 approved (911 CRM + 72 catalog `curated-b2`; 37 + 37 catalog inactive A/B); 23 dòng `f86_installation_2024-04-25` không còn; 808/983 dòng active có `review_blockers`; 786 chunk lá CRM, 130 dưới 80 ký tự, 383 dưới 200.
  `chat_traces` từ lúc nạp lại: 14 lượt website (9 có tra cứu, chỉ trúng catalog, F54 Installation, F54 Operation; `best_similarity` 0,61–0,72), CRM 0 lượt; trace không ghi id chunk nên không đo được chunk đúng từ log thật.
- Kết luận: tiêu chí đạt hiện có 3 tầng (CQ-01…12 + mã chặn; verdict `ok` theo hash; `approved` = thêm cổng 2b không tạm và 2c). Cả ba đo độ trung thực, không đo "tìm được". Chunk đạt là điều kiện cần, không đủ: catalog A và C cùng qua `curate-check` nhưng r@1 core 0,60 so với 0,25/0,60 tuỳ nhãn lát; chunk `ok` chỉ có tiêu đề hình gây bịa (H13); lỗi định tuyến và tên model (10i/10iV) nằm ngoài chunk. Ghi vấn đề mới **I-61**: thiếu cổng "tìm được" theo tài liệu. Chi tiết: [báo cáo](../../reports/chunk_pass_vs_retrieval_2026-11-26.md).
- Ảnh hưởng contract/API/schema: không.
- Chưa kiểm / mở tiếp: Toma quyết tầng D (câu vàng theo tài liệu, ngưỡng), xử lý chunk chỉ-tiêu-đề, duyệt merge S0 trang lai + T-22 rồi nạp `crm-1.7-a`; điền `retrieved_chunk_ids` trong trace (website-qa).

## 2026-11-25 · Catalog: đo tách A (37 cũ), B (37 + làm giàu, không lát), C (72) trên cùng bộ nhãn · loại: đánh giá, thay đổi
- Thay đổi: `curated-build --no-slices` (tham số `model_slices` của `build_chunks`; test `test_without_slices_keeps_the_first_37_chunks_identical`; `pytest tests\doc_ingest` 454 passed). Dựng B = `curated-b3` (`--doc-version 2026-11-26 --vi-keywords --no-slices`).
- Việc ghi DB (Toma cho phép): nạp A (`curated-a`, thêm cột `audience=public` vì file export cũ thiếu cột; `doc_version 2026-11-14`, 37 dòng) và B (37 dòng) cạnh C (72 dòng, `2026-11-25`); mỗi lượt đo bật đúng một phiên bản bằng `is_active`.
  **Trạng thái cuối: C đang active; A và B nằm trong DB ở trạng thái inactive (37 + 37 dòng, không ảnh hưởng tìm kiếm).** Chi phí embed khoảng 0,0006 USD.
- Cùng bộ nhãn (từ git HEAD, `section_path`/hash ánh xạ theo từng phiên bản; nhãn P3 `acceptable` bỏ ở cả bốn điều kiện trừ K02/K05/K16): **A**, **B**, **C0** = C không tính lát, **C1** = C có tính lát (nhãn lát tự động, chưa người duyệt). `--mode all --repeat 2`; 20 câu catalog:

| | core r@1 / MRR | web1 r@1 / MRR / ctx_prec | web2 r@1 / MRR / ctx_prec |
|---|---|---|---|
| A (37 cũ) | 0,60 / 0,722 | 0,55 / 0,699 / 0,423 | 0,65 / 0,764 / 0,417 |
| B (37 + làm giàu) | 0,35 / 0,620 | 0,50 / 0,711 / 0,398 | 0,70 / 0,815 / 0,398 |
| C0 (72, không tính lát) | 0,25 / 0,505 | 0,30 / 0,562 / 0,350 | 0,25 / 0,539 / 0,340 |
| C1 (72, tính lát) | 0,60 / 0,728 | 0,65 / 0,769 / 0,476 | 0,80 / 0,852 / 0,476 |

  Bộ hai nguồn 7 câu (web1 r@1): A 0,714, B 0,857, C0 0,286, C1 0,714; H14 vẫn không thấy chunk đúng ở cả bốn (lỗi định tuyến).
- Theo câu (core, A → B → C1): K10 4 → 2 → 1, K19 9 → 3 → 1, K09 3 → 1 → 1, K15 3 → 2 → 2, K03 4 → 2 → 3, K18 (web1) 5 → 3 → 1; **K16 (liệt kê Mechatrolink) 2 → 2 → 6** (web1 1 → 2 → 5), **K06 (so sánh) 6 → 7 → 10** (web1 4 → 7 → 7);
  **K11 (MPG 6AV) 1 → 4 → 5** và K17 2 → 6 → 4 (core) đã tệ ở B nên do chunk trọn bộ rút gọn và/hoặc `embed_text` làm giàu, không do lát; B làm nhiều câu từ hạng 1 xuống 2 (K01 không, nhưng K08, K12, K14, K18, K20 ở core).
- Đọc kết quả: (1) làm giàu `embed_text` một mình (B) sửa một phần K10, K19, K09, K15, K03 nhưng kéo tụt nhiều câu khác ở core; (2) lát (C) sửa trọn vẹn câu một model hỏi một thuộc tính và cho điểm cao nhất ở đường web (đường production) khi lát được tính là đáp án đúng; (3) lát là nguyên nhân làm K16 và K06 tệ đi;
  (4) C0 cho thấy nếu lát bị coi là "sai" thì C tệ nhất — độ tin của kết luận (2) phụ thuộc nhãn lát tự động. (5) Ba câu K11, K17, K08 cần xem lại chunk trọn bộ rút gọn và dòng "Tóm tắt".
- Chưa làm: gating lát khỏi câu không nêu model/so sánh (cần sửa hàm SQL hoặc retriever production), chunk chỉ mục "tính năng → model" cho câu liệt kê, tách thí nghiệm nhỏ hơn cho làm giàu (chỉ `vi_keywords`, chỉ "Tóm tắt" của bảng), người duyệt nhãn lát. Chưa commit.

## 2026-11-25 · Catalog: nạp `curated-b2` vào Supabase và đo lại bộ câu catalog · loại: thay đổi, đánh giá
- Việc đã làm (Toma cho phép nạp): `load_ingest_run --apply` 72 chunk (`doc_version 2026-11-25`, embed ~0,0006 USD, 72/72 có embedding) rồi `--delete` 37 chunk `2026-11-14` để catalog không trùng. Đã kiểm DB: `qs_product_catalogue` 72 dòng active, `draft`;
  các tài liệu khác không đổi (10iV 122, 6AH 132, 6AVE 133+35, F10T 147+30, F54 148+17, F86 124+23). Sao lưu trước đó (đã chuyển ra ngoài repo): `E:\backups\QS_Technology\doc_chunks_v2_all_2026-11-25.jsonl`.
- Nhãn gold: `catalog_f54_astro.yaml` và `dual_source.yaml` cập nhật `section_path` bảng (hash không đổi), chunk trọn bộ đổi nội dung (nhãn `acceptable` bỏ khi đáp án nằm ở trang riêng model, trừ K02/K05/K16), lát theo model thêm vào `acceptable` cho
  câu nêu model có chunk bảng đúng (tự động theo nhóm hàng, chưa người duyệt). Hai bộ nhãn trước/sau KHÁC NHAU nên chỉ so sánh gần đúng; `mong_doi@1` không so được (chunk "mong đợi" cũ nay thường bị lát acceptable đứng trước).
- Kết quả catalog (20 câu, `--repeat 2`, trước → sau): core:base recall@1 0,65 → 0,60, recall@5 0,90 → 0,90, MRR 0,747 → 0,728; web1:base recall@1 0,65 → 0,65, recall@5 1,0 → 0,95, MRR 0,749 → 0,769, ctx_precision 0,465 → 0,476;
  web2:base recall@1 0,70 → 0,80, recall@5 0,95 → 0,95, MRR 0,785 → 0,852, ctx_precision 0,455 → 0,476. Bộ hai nguồn 7 câu: domain đúng vẫn 0,571 (lỗi định tuyến, không do chunk); core:base recall@5 1,0, web recall@5 0,857.
- Theo câu (core:base, hạng chunk đúng trước → sau): **cải thiện** K10 tuổi thọ dao F86 4 → 1, K19 hệ tọa độ F54 9 → 1, K09 trọn bộ F54 3 → 1, K15 điện áp 10i 3 → 2, K03 look-ahead 10i 4 → 3; **tệ hơn** K16 "model nào hỗ trợ Mechatrolink" 2 → 6,
  K06 so sánh F86/F10T 6 → 10, K11 MPG 6AV 1 → 5, K17 kích thước 6AV (không dấu) 1 → 4, K08 F10T cảm ứng 1 → 2 (một phần do nhãn P3 bị bỏ).
- Đánh giá theo tiêu chí đề xuất ([phương án](../../reports/catalog_rechunk_proposal_2026-11-25.md) mục 5): K10, K19 vào top 2 — **đạt**; recall@1 ≥ 16/20 — đạt ở web2 (0,80), **không đạt** ở core (12/20) và web1 (13/20); không câu nào tụt quá 2 hạng — **không đạt**
  (K16, K11, K17, K06); recall@5 không giảm — đạt ở core và web2, giảm 1,0 → 0,95 ở web1. Kết luận: **lát theo model giúp câu một model hỏi một thuộc tính, nhưng 35 chunk thêm chen vào top 6 của câu liệt kê/không nêu model (K16) và câu so sánh**.
- Việc tiếp (chờ Toma): thử giảm cạnh tranh của lát cho câu không nêu model (giảm số lát/gom lát; hoặc hạ ưu tiên lát; hoặc nhãn `acceptable` đúng cho câu liệt kê: lát của 6AV/6AH/10i chứa Mechatrolink — nhãn bổ sung sau khi thấy kết quả nên cần đánh dấu post-hoc);
  chưa quyết giữ hay lui về 37 chunk (lui = nạp lại `curated-a` bằng `load_ingest_run --apply` từ run cũ). Chưa commit.

## 2026-11-25 · Catalog: phương án C chia lại chunk (lát bảng theo model, chunk trọn bộ gọn, `embed_text` làm giàu) · loại: thay đổi
- Vấn đề: chunk bảng chọn chứa 3–4 model nên không lọc theo model được; ký hiệu ✓/✗ khó khớp câu hỏi; chunk "QS - <MODEL> CONTROLLER" lặp trang riêng model và ghi dải trang `4–19`; hai bảng trùng `section_path`
  ([kiểm duyệt ngược luồng](../../reports/catalog_chunk_audit_2026-11-25.md), [phương án](../../reports/catalog_rechunk_proposal_2026-11-25.md)). Toma chọn phương án C.
- Thay đổi (`doc_ingest/curated/build.py`, `check.py`): (1) thêm **35 lát bảng theo model** (7 model × 5 lát: Tổng quát, Phần cứng, Bù và đa trục, Vận hành và quản lý dao, Điều khiển và lập trình), `content` đúng các hàng như in chỉ lấy cột
  của model (kèm `curated_decisions` của hàng liên quan), `product_models` một model, nối tiếp sau C0036 nên chunk_key C0000–C0036 giữ nguyên; (2) chunk "QS - <MODEL> CONTROLLER" bỏ các dòng lặp với trang riêng model, tên mục thêm "Trọn bộ hệ thống và tùy chọn",
  `page_start/end` = trang trọn bộ, cả hai trang ở cờ `source_pages:4,19`; (3) `embed_text` có dòng "Tóm tắt" đổi ký hiệu ✓/✗/(Option) thành chữ (lát: mọi hàng; bảng gốc: chỉ hàng có ký hiệu) từ nhãn `vi` đã duyệt, không đổi `content`;
  (4) `section_path` bảng gốc duy nhất ("Selection table (F54, F86, F10T, 10S)" và "(6AV, 6AH, 10i)") và "Builder Supp" → "Builder Support" ở `section_path` (nội dung giữ chữ in); (5) `check.content_issues` tính cả trang ở cờ `source_pages:`.
- Kiểm chứng: `pytest tests\doc_ingest` 453 passed (venv ingest; thêm 5 test lát/bảng/trọn bộ/hash); chunk trang riêng model C0000 và C0001 giữ nguyên `content_hash`. Build run mới `curated-b2` (`--doc-version 2026-11-25 --vi-keywords`):
  `curate-check` ĐẠT, **72 chunk** (overview 14, spec 7, table 51), 0 lỗi ràng buộc, 0 vượt 800 token (lát tối đa 710, bảng tối đa 582), 0 dòng có từ lạ, 72 `draft`, verdict 72 `pending`. Loader `--dry-run`: 72 dòng, ~28,9k token embed ≈ 0,0006 USD.
  Run `curated-b` là lần dựng thử bị 2 chunk vượt ngân sách trước khi rút gọn câu "Tóm tắt" của bảng gốc: không dùng.
- Ảnh hưởng contract/schema: không (không đổi `DraftChunk`/SQL; `source_pages` là chuỗi trong `flags`). Chunk P3 (C0002…) đổi `content_hash` nên verdict cũ không giữ; P1/P2 và bảng gốc giữ hash.
- **Chưa làm / chờ:** nạp `curated-b2` vào DB (`--apply` thêm phiên bản 2026-11-25; phải gỡ phiên bản 2026-11-14 để không trùng; cần Toma đồng ý vì ghi Supabase thật) rồi đo lại bộ câu catalog; điền verdict; sửa nhãn gold của chunk bảng (`section_path` đổi);
  biên soạn trang 15–16, 22–24, 2, 18; từ vựng `spec_attributes` mới cần sửa registry chatbot (chưa thêm); C-11 (RLTR/RBT-01). Chưa commit.

## 2026-11-25 · Ảnh lồng trong ô bảng không còn bị liệt kê thành asset (publish-assets báo "chưa render") · loại: sự cố, thay đổi
- Vấn đề: `publish-assets` (chế độ lập kế hoạch) báo 6 ảnh chưa render ở 6AH (B0006: tr.11 e018, e022; tr.14 e032, e035, e038) và 10iV (B0008: tr.14 e010); lỗi có sẵn ở `crm-1.2-a`, không do luật mới.
- Nguyên nhân: 6 ảnh là biểu tượng phím nằm trong ô bảng phím (phần tử cha là `table_segment`). T-14 (`normalize/figures._crops`) chỉ render ảnh cấp ngoài (`parent_id is None`), nên ảnh lồng không có `image`, nhưng `build/fields._assets` vẫn liệt kê chúng thành asset không có `local_path`.
- Sửa (chưa commit): `build/fields._assets` bỏ qua phần tử hình lồng (có phần tử cha) không có file ảnh; test `test_nested_picture_without_image_is_not_a_separate_asset` trong `test_chunker.py`. `pytest tests\doc_ingest` 448 passed (venv ingest), 434 passed + 14 skipped (venv chính).
- Kiểm chứng: dựng `crm-1.6-b` cho 6AH và 10iV (sao chép từ `crm-1.6-a`, carry verdict 132/132 và 122/122, nội dung chunk không đổi); kế hoạch publish 0 vấn đề (149 và 125 ảnh). Trong DB, chunk 6AH B0006 và 10iV B0008 vẫn còn asset không có file cho tới khi nạp lại từ `crm-1.6-b`.
- Đã nạp lại (Toma đồng ý, 2026-11-25): `load_ingest_run --apply` cho 6AH (xoá 132, chèn 132) và 10iV (xoá 122, chèn 122) từ `crm-1.6-b`, mọi chunk vẫn `draft`, embed khoảng 0,0007 USD; `source_run` của hai tài liệu trong DB là `crm-1.6-b`.
- Mở tiếp: Toma quyết commit bản sửa; `publish-assets --apply` cho 6AH và 10iV dùng `crm-1.6-b` (8 run còn lại giữ như cũ).

## 2026-11-25 · Nạp lại toàn bộ chunk CRM vào Supabase (draft), xoá chunk cũ đang active · loại: thay đổi, quyết định
- Vấn đề: DB giữ 1.173 chunk active từ `crm-1.0-a` (bản cũ chưa sửa lỗi) và bản thử `f54_operation_v02`; cần thay bằng chunk đã sửa, chưa mở `approved` nào (chờ cổng 2b/2c).
- Quyết định (Toma, 2026-11-25): xoá chunk `is_active = true` là chunk trích từ file nguồn bản cũ; nạp toàn bộ ở trạng thái `draft`; không cần bước làm giàu trước khi nạp (embed từ `embed_text`; làm giàu có thể bổ sung sau bằng nạp lại cùng `doc_id` + `doc_version`). Tôi giữ nguyên 37 chunk catalogue `source=manual` (biên soạn tay, không phải chunk trích bản cũ) và 23 dòng inactive; chưa hỏi lại Toma về hai nhóm này.
- Thực hiện: sao lưu toàn bảng (1.203 dòng, không embedding) → `E:\backups\QS_Technology\doc_chunks_v2_all_2026-11-25.jsonl` (ngoài repo); `chunking_loader.load_ingest_run --dry-run` rồi `--apply` cho 10 tài liệu (mỗi tài liệu một transaction thay bản cũ cùng `doc_id` + `1.0`): 911 dòng, embed 0,003 USD, 0 lỗi; sau đó xoá 295 dòng active của `f54_operation_v02`. Run đã nạp: F86/F54 Installation `crm-1.4-a`, 6AVE/F10T Installation và F10T Operation `crm-1.2-a`, F86/F54/6AH/6AVE/10iV Operation `crm-1.6-a` (không dùng `crm-1.7-a` vì S0 trang lai và T-22 chưa được duyệt merge).
- Kết quả: `doc_chunks_v2` 971 dòng (948 active), 0 approved; mọi chunk CRM `draft` có embedding (chunk cha không embed theo D-008), chat với `RETRIEVAL_APPROVED_ONLY=true` chưa tìm thấy tài liệu CRM nào.
- Còn lại: ảnh của chunk chưa `publish-assets` cho run mới; thư mục sao lưu chưa gitignore (không commit); khi mở `approved` cần cơ chế gỡ `ocr_required` (I-53), cổng 2b, cổng 2c.

## 2026-11-25 · Giai đoạn 1b: khôi phục tiêu đề bị OCR hỏng (T-22) và ép OCR trang lai (S0), chưa merge · loại: thay đổi, kiểm chứng
- Vấn đề: 10 chunk lá `fix` của 5 bản Operation (mục 3.4.2 gắn nhầm 3.4.1, chunk 3.9.2 lẫn Note của 3.10). Khảo sát cho thấy hai nguyên nhân khác nhau, không phải một luật "khôi phục tiêu đề": (A) tiêu đề 3.4.2 của F86, 6AVE, 10iV bị OCR đọc thành `ES    S    EM` (mục lục không có trong dữ liệu để khôi phục); (B) trang "3.10 SYSTEM SETTING" (mỗi bản một trang) có text layer "ok" 321 ký tự nhưng tiêu đề, đoạn dẫn, bảng là ảnh raster nên không được OCR, chữ mất ngay từ bước đọc.
- Quyết định/luật (đề xuất, chưa merge, chờ Toma): **S0 trang lai**: tài liệu có ≥ 70% trang cần OCR, trang có text layer `ok` nhưng bitmap ≥ 10% và ≤ 700 ký tự → `text_layer: hybrid`, ép OCR (ngưỡng `hybrid_*` trong `Thresholds`). **T-22**: `text_patches` trong `table_patches/<doc_id>.yaml` thay nguyên văn một dòng Docling (khớp đúng một dòng trên trang, nếu không thì review chặn `text_patch_unmatched`; log T-22); phát hiện tiêu đề hỏng `heading_garbled` (review chặn chunk): section_header trên trang OCR có vùng chữ ≥ 25 pt/ký tự và chuỗi khoảng trắng liên tiếp. 3 vá `proposed` (F86 tr.58, 6AVE tr.70, 10iV tr.71) có bằng chứng OCR lại vùng tiêu đề ở 2x và 3x trùng nhau, và ảnh trang 10iV tr.71.
- File (chưa commit): `s0.py`, `schemas/{run,profile,table_patch}.py`, `table_patch_io.py`, `normalize/text_patches.py` (mới), `normalize/recorder.py`, `schemas/normalized.py`, `pipeline.py`; `table_patches/{f86,6ave,10iv}-operation-en.yaml`; test `test_t22_text_patches.py` (4), `test_s0.py` (+2), `test_table_patches.py`.
- Kiểm chứng: `pytest tests\doc_ingest` 447 passed (venv ingest), 433 passed + 14 skipped (venv chính). Parse lại chỉ các trang lai bằng OCR ép buộc (10iV tr.32 và 96, F54 tr.80 và 95, 6AH tr.89, 6AVE tr.96, F86 tr.83), ghép vào raw cũ, dựng run `crm-1.7-a` (carry từ `crm-1.6-a`; run cũ giữ nguyên). Kết quả: tiêu đề 3.4.2 đã vá; mục 3.10 SYSTEM SETTING có tiêu đề, đoạn dẫn, bảng thư mục, Notes; chunk 3.9.2 không còn lẫn Note của 3.10; 10iV tr.32 và F54 tr.95 có thêm chữ thật (câu "Control cable must have a shield wire…", Step 2-3 của F54) thay cho mảnh rác; 57 chunk lá đổi, không còn `heading_garbled` hay `text_patch_unmatched`; thêm `text_coverage_gap` ở 10iV tr.32 (OCR không khớp lớp chữ ẩn của trang).
- Duyệt: F86 tay đối chiếu ảnh (10 chunk: 9 `ok`, 1 `fix` S2: câu cảnh báo "If the directory names or formats are incorrect…" vỡ OCR); tài liệu khác suy theo nội dung tương đương hoặc `content_hash` đã `ok`; 9 chunk còn lại duyệt riêng (F54 B0111 ảnh thành bảng, B0134 lẫn chữ rác ảnh phần mềm; 6AH B0108 Step 2 vỡ, mất mật khẩu, S1; 10iV B0104 câu mở đầu vỡ). Verdict của Claude, chưa người xác nhận. Tổng 10 tài liệu: 925 chunk, `ok` 623, `fix` 291, `pending` 8 (trước: 911 / 596 / 307 / 8).
- Còn lại: các luật chưa commit; một số câu trong ảnh trang lai vẫn OCR vỡ (RapidOCR đọc hỏng đoạn chữ xám nhỏ); F10T Operation chưa hưởng lợi.
- Mở tiếp: Toma duyệt merge S0 trang lai và T-22 và xác nhận 3 vá tiêu đề; sau đó Giai đoạn 2 (I-56).

## 2026-11-25 · Giai đoạn 1 (tiếp): merge T-20b, dựng lại 5 bản Operation (`crm-1.6-a`) và duyệt 77 chunk đổi · loại: kiểm chứng, thay đổi
- Quyết định (Toma đồng ý merge sau dry-run): T-20b vào `feature/deploy_ai_service`, commit `aba3a6d` (chưa push). Dựng lại F86, F54, 6AH, 6AVE, 10iV Operation thành run mới `crm-1.6-a` (có ảnh, `--carry-review` từ `crm-1.2-a`): 659 chunk (trước 638), 104 chunk về `pending` (77 lá + 27 cha); `crm-1.2-a` giữ nguyên.
- Duyệt: 5 agent đối chiếu 77 chunk lá với ảnh trang (verdict của model, chưa người xác nhận); Claude kiểm lại các ca "thiếu Note": 6 báo cáo (F86 B0057, F54 B0056 và B0126, 6AH B0060, 6AVE B0066, 10iV B0057) thực ra là tách chunk, Note/Step 5/tiêu đề nằm ở chunk con kề (đã xác nhận trong dữ liệu và ảnh F86 tr.51), nên ghi `ok` S3 `[note_split]`. Kết quả lá: 67 `ok`, 10 `fix` (lỗi thật): mục 3.4.2 bị gắn nhầm mục 3.4.1 và mở đầu bằng rác OCR "ES S EM" (F86 B0066, B0067; 6AVE B0075; 10iV B0066, B0067); chunk 3.9.2 mất tiêu đề (OCR thành "Astro 10i"/"ASTRO 6AV") và lẫn Note macro `.txt` của mục 3.10 (F86 B0103, 10iV B0103, 6AVE B0112, F54 B0106, 6AH B0109; 6AH B0109 còn Step 2 vỡ OCR, mất mật khẩu, S1). Chunk cha: 16 `ok`, 11 `fix` (suy ra từ con). Không còn `pending` ở 5 bản này; sao lưu `chunk_review.json.bak-before-gd1`.
- Số liệu mới của 5 bản Operation: `fix` 201 → 155 (6AH 46→34, 6AVE 39→29, 10iV 39→30, F54 45→41, F86 32→21). Toàn bộ 10 tài liệu: 911 chunk, `ok` 596, `fix` 307, `pending` 8 (cha F10T Operation); trước giai đoạn này 522 / 353 / 15 trên 890 chunk.
- Còn lại: chunk con `Note:` đứng riêng 73 ký tự (loại `overview`) và dòng "Memo / Model: …" xen trong thân (S3, chưa luật); 10 chunk lỗi thật nhóm 3.4.2 và 3.9.2; F10T Operation (OCR sai dấu, nhãn "Bước") chưa được lợi từ T-20b.
- Mở tiếp: luật khôi phục tiêu đề bị OCR hỏng (mục 3.4.2, 3.9.2: tiêu đề được thay bằng tên model hoặc rác) và tách Note của mục kế khỏi chunk trước; sau đó Giai đoạn 2 (I-56).

## 2026-11-25 · Giai đoạn 1: luật T-20b (khung "Memo" trên trang OCR, I-59), dry-run, chưa merge · loại: thay đổi, kiểm chứng
- Vấn đề: 58 chunk lá mất Step 1–2/Note (I-59) ở 5 bản Operation. Chữ Step/Note có trong dữ liệu thô nhưng nằm trong picture "Memo" và bị gắn `figure_text`; T-20 chỉ chạy trên trang có text layer, các tài liệu này là ảnh/OCR toàn bộ (S0 `text_layer: missing`). 79 picture chứa nhãn "Step N" chưa được trả về thân.
- Quyết định/luật (đề xuất, chưa merge, chờ Toma): T-20b: trên trang OCR (S0 biết là OCR), picture là khung chữ khi có con là nhãn bước ("Step N:", `chunking.step_patterns`); chỉ trả về thân các con nằm trong cột của nhãn bước (x0 ≥ x0 nhỏ nhất của nhãn bước − 12 pt, tránh trả chữ của ảnh chụp màn hình trong picture phủ hai cột, F54 trang 78); picture đã thuộc luật `side_column` (I-59 cũ) giữ nguyên; chữ trả về không tính vào lề trái văn bản (`RawItem.frame_released`, tránh lệch T-18). Cờ `text_frame_ocr`. Profile `default.yaml`: thêm "memo" vào `frame_label_patterns`. Trang có text layer và thiếu S0: không đổi.
- File (chưa commit): `normalize/figures.py`, `normalize/docling_reader.py`, `pipeline.py`, `profiles/default.yaml`; test `test_t20b_ocr_memo.py` (7 test), `test_text_frames.py` (test cũ "OCR không giải phóng" tách thành "thiếu S0 không giải phóng").
- Kiểm chứng: `pytest tests\doc_ingest` 441 passed (cả venv ingest và venv chính). Dry-run 14 mục (bản gốc = HEAD `ac4c861`, đã có B1/T-21): chỉ 5 bản Operation đổi (65 chunk lá cũ → 77 mới); 51 chunk cũ thuộc I-59, 8 thuộc chunk_split thủ tục (cùng cụm bước), 6 đang `ok` (chunk kề chứa Step 2 bị gộp lại); Installation, F10T Operation và 4 bộ cũ không đổi; bảo toàn chữ/cell đạt (ALL CONSERVED). Hai lần chạy đầu phát hiện lỗi: dương tính giả F54 tr.78 (chữ ảnh màn hình bị trả về thân) và lề trái lệch ở 10iV tr.10 (5 dòng "Model: …" bị gắn vào hình); sửa bằng giới hạn cột bước và cờ `frame_released`, chạy lại: hết cả hai.
- Còn lại: chunk `Note:` sau Step tách thành chunk riêng (10iV B0047); dòng "Memo / Model: …" của khung thứ hai còn lọt vào thân ở trang OCR (T-20 gắn nhãn khung lỏng chỉ chạy trên trang text layer); 7 trang I-59 mỗi bản không có picture chứa nhãn bước (nguyên nhân khác); F10T Operation chưa hưởng lợi (nhãn "Bước", OCR sai).
- Mở tiếp: Toma duyệt merge T-20b; dựng lại 5 bản Operation (run mới) và duyệt lại 77 chunk đổi theo PDF.

## 2026-11-25 · Giai đoạn 0 của kế hoạch fix/pending: quyết chính sách và áp chuẩn I-58 · loại: quyết định, thay đổi
- Vấn đề: bốn bản Installation duyệt `ok` 56 chunk sơ đồ chỉ có caption, còn các bản Operation xếp `fix` 106 chunk I-58; trong 106 chunk có 42 chunk mất chữ thật hoặc OCR vỡ, 64 chunk chỉ thiếu nội dung nằm trong ảnh (ánh xạ màu dây-chân cảm biến, nhóm chân CX, CN2 tay quay).
- Quyết định/luật (Toma, 2026-11-25): (1) chunk sơ đồ mà chi tiết chỉ nằm trong ảnh là `ok` kèm cờ `image_only_info` khi chữ trong chunk khớp 100% phần PDF có dạng chữ; mất chữ thật vẫn `fix`. (2) Biên soạn tay: mở rộng lớp vá ô T-21 và thêm vá cho chunk (chưa làm). (3) Không xin CRM PDF có text layer; tự OCR lại tiếng Việt cho F10T và OCR ép buộc cho 10iV tr.107–110. (4) Cơ chế gỡ `ocr_required` (I-53) làm sau khi nội dung chunk ổn định.
- Thay đổi dữ liệu: 64 chunk (6AVE Operation 19, F54 Operation 18, 10iV 13, 6AH 13, F86 Operation 1) đổi `fix` → `ok`, ghi chú bắt đầu bằng `[image_only_info]`, reviewer ghi chính sách GĐ0 (chưa người xác nhận từng chunk); sao lưu `chunk_review.json.bak-before-gd0` trong `crm-1.2-a` của 5 tài liệu. Chọn chunk bằng quy tắc theo từ khóa trong ghi chú đối chiếu (loại chunk có dấu hiệu mất chữ/OCR vỡ và S1): có thể lọt một số chunk còn chuỗi rác OCR (vd. `f86-operation-en:B0011` còn chuỗi 'i- ns dpn'); kiểm mẫu 8/8 là sơ đồ chỉ trong ảnh. Chưa thêm trường `image_only_info` vào schema chunk/DB: cờ mới nằm trong ghi chú verdict.
- Kết quả: tổng 10 tài liệu `ok` 522, `fix` 353, `pending` 15 (cha); trước đó 451 / 417 / 22.
- Mở tiếp: Giai đoạn 1 (luật I-59); cần xác định cách đưa cờ `image_only_info` vào metadata chunk khi nạp DB; chunk sơ đồ `ok` vẫn yếu khi tra cứu, chat chỉ cho người dùng xem ảnh chứ không tự đọc chi tiết trong ảnh.

## 2026-11-25 · Kế hoạch xử lý chunk `fix`/`pending` và thử làm giàu bằng ảnh · loại: đánh giá, quyết định
- Vấn đề: 417 chunk `fix`, 15 `pending` (cha); cần thứ tự xử lý, và cần biết làm giàu bằng ảnh có đáng làm không.
- Quyết định/luật: lập kế hoạch 6 giai đoạn ([p4_fix_pending_plan_2026-11-25.md](../../reports/p4_fix_pending_plan_2026-11-25.md)); chưa đổi mã. Nguyên nhân chính của 302 lá đã phân loại: I-58 sơ đồ chỉ còn caption 97, I-59 ảnh nuốt chữ thủ tục 58, I-51 43, I-29 32, I-56 30, chunk_split 13, I-57 14, I-60 7. Hai bản Installation và các bản Operation đang dùng hai chuẩn khác nhau cho chunk sơ đồ chỉ có caption (`ok` so với `fix`): cần Toma chốt chuẩn chung (Giai đoạn 0).
- Thử làm giàu bằng ảnh (gpt-4.1-mini, scratchpad, không ghi vào run): 22 ảnh, ≈ 0,002 USD mỗi ảnh. Ảnh màn hình/thao tác: nội dung đúng ở 4/4 ảnh đã đối chiếu ảnh gốc, cần lọc giá trị phụ (giờ, tên file). Sơ đồ đấu dây: cho phép nêu quan hệ thì sai 2/5 (CN9/CN10 đảo, chân OUT A/B sai), cấm thì FAQ không trả lời được (~40% trả lời được). Bản vẽ kích thước: gán nghĩa số đo không ổn định qua 3 lần chạy. Chưa có số đo hiệu quả tra cứu.
- Mở tiếp: Toma chốt chính sách Giai đoạn 0 (chuẩn chunk sơ đồ chỉ caption, I-53, cách biên soạn tay, xin PDF text layer); sau đó theo kế hoạch; nghiên cứu làm giàu theo mục 6 của kế hoạch.

## 2026-11-25 · Hướng B cho I-53: đo cổng 2b và làm giàu 2c trên F54/F86 Installation · loại: thay đổi, kiểm chứng
- Vấn đề: để chunk lên `approved` cần cổng 2b (đo ranh giới), cổng 2c (làm giàu) và gỡ review chặn; thử trên hai tài liệu Installation sạch nhất.
- Quyết định/luật (Toma chọn hướng B): soạn nhãn ranh giới `tests/doc_ingest/fixtures/eval/{f54,f86}-installation-en.chunks.json` (từ cấu trúc tiêu đề mục, `verified=false`); chạy `build --labels` rồi `enrich`; nâng prompt làm giàu v4 → v5 (thêm quy tắc cho chunk chỉ có tiêu đề hình: không hỏi giá trị, chức năng, ý nghĩa). Chưa làm cơ chế gỡ `ocr_required` (xem Mở tiếp).
- File: `enrich/prompt.py` (v5), `tests/doc_ingest/test_enrich.py` (phiên bản v5), 2 file nhãn nháp. Run mới (không ghi đè): `crm-1.4-a` (F54, F86: nhãn ranh giới), `crm-1.5-a` (F86: làm giàu v5).
- Kiểm chứng: 2b: precision 1,0 / recall 1,0 cả hai tài liệu; F86 cổng 2b ĐẠT (tạm vì nhãn chưa xác nhận); F54 không đạt do 1 `fix` mở (trang bìa, logo OCR). `pytest tests\doc_ingest` 434 passed. 2c, F86: v4 (crm-1.4-a) 18/23 ok (5 FAQ hỏi giá trị không có trong chunk); v5 (crm-1.5-a) 9/23 ok, 14 fix không nặng: 13 chunk chỉ có tiêu đề hình (< 100 ký tự) sinh FAQ chung chung hoặc hỏi về chính sơ đồ, 1 FAQ vô nghĩa ở B0006; cổng 2c KHÔNG ĐẠT. Chi phí LLM ≈ 0,006 USD mỗi lần. Verdict là của Claude, chưa người xác nhận.
- Ảnh hưởng contract/API/schema: prompt làm giàu đổi phiên bản (verdict 2c cũ hết hạn khi làm giàu lại); không đổi schema, SQL, API.
- Mở tiếp: Toma quyết chính sách chunk chỉ có tiêu đề hình (13/23 chunk F86, 12/17 F54): bỏ FAQ, hoặc không làm giàu, hoặc gộp vào chunk mục cha; xác nhận nhãn ranh giới (`verified=true`); quyết chunk bìa F54 (S3); sau đó mới làm cơ chế gỡ `ocr_required` (I-53 điều kiện 1) và làm giàu F54.

## 2026-11-25 · Xác nhận 13 vá T-21, duyệt 7 chunk bảng cổng, chẩn đoán I-53 · loại: kiểm chứng, quyết định
- Vấn đề: lớp vá ô (mục dưới) còn `proposed`, 7 chunk bảng cổng của `crm-1.3-a` còn `pending`, và I-53 (không chunk nào lên `approved`) chưa có hướng.
- Quyết định/luật: Toma chỉ thị xác nhận 13 vá và duyệt 7 chunk. Đối chiếu lại ảnh trang F54 tr.7–9, F86 tr.6–11: 13 vá đúng, 7 chunk `ok`. Các lỗi in sẵn trong PDF được giữ nguyên văn (F54 "DIR+" ở CN10; F86 "420mA", "(D3+)" ở D5-, "X40 – X47" ở CN17, dấu "-" thừa sau CN13). Một lỗi nhỏ còn lại: F86 CN15 mất dấu "-" trước X47 (chân đủ, không đổi nghĩa). 13 vá đổi sang `status: verified`, `verified_by` ghi chỉ thị của Toma và đối chiếu ảnh của Claude (chưa có người đối chiếu ảnh trực tiếp). Verdict ghi vào `chunk_review.json` của `crm-1.3-a`, reviewer "Claude PDF recheck … theo chỉ thị của Toma".
- File: commit `c3b1177` (chưa push): lớp vá T-21 và 13 vá; `table_patches/*.yaml` thêm `status`, `verified_by`.
- Kiểm chứng: `pytest tests\doc_ingest` 434 passed. Trạng thái sau duyệt: F54 Installation 16 ok, 1 fix (bìa, logo OCR); F86 Installation 23 ok (1 còn chặn `ocr_required`). Tổng 10 tài liệu: 451 ok, 417 fix, 22 pending trước bước này (417 fix gồm cả chunk cha; 372 là chunk lá).
- Chẩn đoán I-53: `approved` cần cả ba điều kiện (`export/doc_chunks_v2.review_status`): (1) không có `review_blockers`; (2) cổng 2b đạt và không tạm: cần đo precision/recall ranh giới (hiện null) và 0 `fix` mở; (3) làm giàu `approved` cho chunk không phải cha (hiện `none`). Gỡ mã chặn chỉ giải quyết (1); chunk F54/F86 Installation không bị chặn vẫn `draft` vì thiếu (2) và (3). Chưa đổi mã.
- Mở tiếp: Toma quyết cách xử lý (2) và (3) trước khi làm cơ chế gỡ chặn I-53; xem STATE.

## 2026-11-25 · Merge T-15b và lớp vá ô thủ công T-21 cho bảng cổng Installation (F54, F86) · loại: thay đổi, quyết định

- Vấn đề: sau dry-run (mục dưới), cần chốt luật nào vào nhánh chính và có cách sửa các lỗi gán sai chân đã nằm sẵn trong raw Docling (X47/Y40/CY0 của F54; FG, mô tả CN2–CN4, X57 của F86), vì luật chung cho lỗi này (B4) đã bị loại.
- Quyết định/luật (Toma, 2026-11-25): **merge T-15b** (B1) vào `feature/deploy_ai_service`; **không merge T-04b** (B2b, giá trị thấp, bỏ khỏi mã); soạn **lớp vá ô** thay B4. T-21: file `table_patches/<doc_id>.yaml`, mỗi vá sửa một chuỗi con trong một ô, xác định bằng (trang, khoá hàng, cột), chuỗi cần thay phải xuất hiện đúng một lần; không khớp thành review chặn chunk `table_patch_unmatched`; mỗi vá ghi log `T-21` (before/after nguyên văn ô, bằng chứng, status) và cờ `cell_patched:<id>` trên bảng. Status `proposed` cho tới khi người xác nhận.
- File: commit `a0ce51a` (chưa push): `normalize/tables.py` (T-15b, điều kiện: trang liền kề, hàng dữ liệu đầu đoạn, hàng đích có ô khoá, chữ nối tiếp không bắt đầu bằng chữ hoa) + `tests/doc_ingest/test_t15b.py` (5 test). Chưa commit (lớp vá ô): `schemas/table_patch.py`, `table_patch_io.py` (nạp YAML, ngoài `normalize/` vì test PI-04), `normalize/table_patches.py` (T-21), `pipeline.py`, mã review mới `table_patch_unmatched` (`schemas/normalized.py`, `normalize/recorder.py`, `report/quality_summary.py`), `table_patches/f54-installation-en.yaml` (4 vá), `table_patches/f86-installation-en.yaml` (9 vá), `tests/doc_ingest/test_table_patches.py` (6 test).
- Kiểm chứng: `pytest tests\doc_ingest` 434 passed (venv ingest), 420 passed + 14 skipped (venv chính). Dựng `crm-1.3-a` cho F54 và F86 Installation (B1 + vá, có ảnh): 13/13 vá áp, 0 `table_patch_unmatched`, 0 `orphan_row`, CQ không lỗi; danh sách chân của CN7, CN6, CN5, CN4, CN2, CN1 (F54) và CN2, CN3, CN5, CN15, CN16, CN17 (F86) khớp ảnh trang; chỉ các chunk bảng cổng bị vá đổi nội dung (F54 B0004, B0005; F86 B0003, B0005–B0008) và về `pending`, các chunk còn lại giữ verdict (carry từ `crm-1.2-a`: 15/17 và 18/23).
- Ảnh hưởng contract/API/schema: thêm luật T-15b, T-21 và mã review `table_patch_unmatched` vào chuẩn hoá (chưa cập nhật `p1_normalization_contract.md`); không đổi SQL, API, chat.
- Mở tiếp: Toma xác nhận 13 vá (status `proposed`) và cho commit lớp vá; duyệt lại 7 chunk `pending` của `crm-1.3-a`; F10T Installation (X57 CN17/CN18, mô tả CN4/CN5, CN8) và 6AVE Installation (hàng CN7/CN8/CN9 bị gộp một hàng, cần tách hàng, ngoài khả năng của vá chuỗi) chưa vá; build lại các tài liệu còn lại với B1 (hàng nối tiếp Installation đã hết, còn 23 hàng mồ côi Operation); cập nhật contract chuẩn hoá.

## 2026-11-25 · Dry-run luật T-15b (hàng nối tiếp qua trang) và T-04b (nhãn cột bảng tham số) trên nhánh `claude/rule-dryrun-b1-b2` · loại: đánh giá, kiểm chứng

- Vấn đề: 39 chunk lỗi I-56/I-56b (hàng nối tiếp qua trang mất tên cổng) và 17 chunk bảng tham số tách không có tiêu đề cột; cần biết luật mới ảnh hưởng gì trước khi merge.
- Quyết định/luật (Toma duyệt kế hoạch 2026-11-25): dry-run, chưa merge luật nào; tiêu chí: chỉ đổi trong tập chunk dự kiến, `tests\doc_ingest` qua, baseline F86 không đổi; không làm luật tổng quát cho lỗi gán sai chân (B4), thay bằng biên soạn tay bảng cổng Installation. B2 (lặp tiêu đề cột khi tách bảng) hoá ra đã có trong chunker (`_table_units`); thay bằng T-04b nhãn cột từ profile cho bảng tham số không có header.
- File: nhánh `claude/rule-dryrun-b1-b2` (chưa commit): `normalize/tables.py` (T-15b `_carry_target`, T-04b `apply_profile_header`), `schemas/profile.py` (`param_table_columns`), `schemas/normalized.py` (`Column.header_source` thêm `"profile"`), `profiles/qs_controller.yaml`, `tests/doc_ingest/test_t15b_t04b.py` (7 test). Báo cáo: [p4_t15b_t04b_dryrun_2026-11-25.md](../../reports/p4_t15b_t04b_dryrun_2026-11-25.md).
- Kiểm chứng: dry-run 14 mục (10 tài liệu CRM + F54/F86/F10T cũ) bản gốc vs bản sửa: 51/774 chunk lá đổi (22 bảng cổng Installation, 30 bảng tham số chương 4, +1 chunk F10T), toàn bộ trong tập dự kiến; `orphan_row` Installation 11→0 (F86 cũ 3→0), Operation giữ 23; chunk `table_no_header` Operation 7–8→1–2; 10iV, `f54/eval-m`, `f86/eval-j` không đổi; bảo toàn chữ và cell ở cả 14 mục. `pytest tests\doc_ingest` 430 passed (venv ingest), 416 passed + 14 skipped (venv chính); `test_f86_baseline` qua; cổng `chunk_quality.json` F54/F86 cũ giữ nguyên. B1 vòng 1 gộp nhầm một hàng bảng chú giải phím 10iV, vòng 2 (tỷ lệ ô khoá rỗng) sai hướng, vòng 3 (chữ nối tiếp không bắt đầu bằng chữ hoa) đạt.
- Ảnh hưởng contract/API/schema: chỉ trong nhánh làm việc, chưa merge: thêm luật T-15b, T-04b, trường profile `param_table_columns`, giá trị `header_source="profile"`.
- Mở tiếp: Toma quyết merge T-15b (đề xuất có) và T-04b (giá trị thấp); build lại `crm-1.3-a` và duyệt lại 51 chunk sau khi merge; cơ chế biên soạn tay bảng cổng (lớp vá ô hay mở rộng `curated/`); 23 hàng mồ côi Operation (13 hàng đầu bảng, 9 giữa trang) chưa xử lý.

## 2026-11-25 · Đối chiếu đợt 2: 6 tài liệu CRM còn lại (`crm-1.2-a`), tổng 372 chunk đã duyệt · loại: đánh giá, kiểm chứng

- Vấn đề: đối chiếu nốt 6 tài liệu (`6ave-installation-vi`, `f10t-installation-vi`, `10iv-operation-en`, `6ave-operation-en`, `6ah-operation-en`, `f10t-operation-vi`) theo quy trình đã chốt.
- Quyết định/luật: không đổi luật, code hay DB. Dựng `crm-1.2-a` cho 6 tài liệu (run 14–103 s, build bằng venv có `tiktoken`; verdict chép 25/35, 18/30, 109/117, 121/130, 115/128, 108/147). `f10t-operation-vi` chỉ duyệt mẫu 55/115 chunk theo kế hoạch (tất cả bảng/alarm/parameter/pending + mỗi 5 chunk hình/overview); 60 chunk còn lại giữ verdict cũ. 29 chunk F10T rớt dấu tiếng Việt (I-29) được agent xếp "dùng được" nhưng giữ verdict `fix`; các tài liệu khác `fix_minor` và `false_positive` đổi sang `ok`.
- File: phần "Đợt 2" trong [p4_crm_fix_recheck_result_2026-11-25.md](../../reports/p4_crm_fix_recheck_result_2026-11-25.md); verdict trong `crm-1.2-a/build/chunk_review.json` (có `.bak-before-recheck`) và `fix_recheck.csv`.
- Kiểm chứng: 255 chunk đợt 2 do 5 subagent đối chiếu ảnh trang; Claude kiểm mẫu 1–2 chunk mỗi tài liệu (mở ảnh trang 12 của F10T Installation, còn lại qua nội dung chunk). Kết quả đợt 2: 189 lỗi xác nhận, 56 dùng được kèm ghi chú, 10 báo động giả. Cả 10 tài liệu (372 chunk): 280 / 79 / 13; S1 72, S2 202, S3 85; nhóm nguyên nhân: I-58/I-57 120, I-59 59, I-51 42, I-56/I-56b 39, bảng bị tách 14. Nổi bật: 10iV chương 4 mất chữ số (I-55), X57 gán sai CN17/CN18 (F10T), hàng "9" thành "6" ở bảng chú thích hình 3-1 (6AVE, 10iV, F86), F10T 45/46 chunk chữ Việt rớt dấu (I-29).
- Ảnh hưởng contract/API/schema: không.
- Mở tiếp: Toma duyệt luật (T-15b, I-56, heading chương hỏng, I-55 cho 10iV, bảng chú thích hình), chính sách chunk hình chỉ có caption, xác nhận mẫu verdict (đặc biệt 72 chunk S1), I-53; parse lại raw 10iV; kiểm xem F10T có text layer thay OCR được không; 60 chunk F10T chưa duyệt; chunk `ok` cũ và chunk cha; mục 4.5 MACRO PARAMETER; lỗi nguồn PDF cần báo tác giả.

## 2026-11-25 · Đối chiếu xong đợt 1: 117 chunk `fix`/`pending` của F54 + F86 (`crm-1.2-a`) · loại: đánh giá, kiểm chứng

- Vấn đề: tiếp phần 2–4 của quy trình (mục dưới): duyệt `f86-installation-en`, `f86-operation-en`, `f54-operation-en` với ảnh trang.
- Quyết định/luật: không đổi luật, code hay DB. Verdict là đề xuất của model, chưa người xác nhận: Claude duyệt trực tiếp 2 bản Installation; 2 bản Operation do 2 subagent duyệt rồi Claude kiểm mẫu trên ảnh trang (2 chunk mỗi bản, 4/4 đúng); `reviewer` ghi rõ trong `chunk_review.json`.
- File: [p4_crm_fix_recheck_result_2026-11-25.md](../../reports/p4_crm_fix_recheck_result_2026-11-25.md); ghi verdict vào `crm-1.2-a/build/chunk_review.json` (có `.bak-before-recheck`) và `_summary/recheck-2026-11-25/fix_recheck.csv`.
- Kiểm chứng: 117 chunk (3 + 6 + 37 + 71) mở ảnh trang đối chiếu: 91 `fix` xác nhận, 23 dùng được kèm ghi chú, 3 báo động giả; S1 32, S2 56, S3 26. Nhóm nguyên nhân (chunk `fix`): I-58/I-57 38, I-59 19, I-51 16, I-56/I-56b 13, bảng bị tách 5. Hành động đề xuất: `manual_curate` 51, `rule_fix` 38, `re_ocr` 15, `merge` 6, `drop_chunk` 4. Lỗi S1 đã kiểm trên ảnh: X47/Y40/CY0 (F54 Installation), X57 (F86 Installation), số hàng 9→6 (F86 Operation B0040), `6: port 6` sang hàng #4160 (B0108), mất IP 192.168.1.225 (F54 Operation B0129).
- Ảnh hưởng contract/API/schema: không.
- Mở tiếp: Toma duyệt T-15b, hướng xử lý I-56, chính sách chunk hình chỉ có caption, xác nhận mẫu verdict (đặc biệt 32 chunk S1) và I-53; chưa kiểm chunk `ok` cũ và chunk cha, mục 4.5 MACRO PARAMETER (F54 Operation tr.106); 6 tài liệu CRM còn lại chưa đối chiếu; danh sách lỗi nguồn PDF (báo tác giả) nằm trong báo cáo.

## 2026-11-25 · Quy trình đối chiếu chunk `fix` đã chốt; run `crm-1.2-a` (F54, F86); duyệt `f54-installation-en` · loại: quyết định, kiểm chứng

- Vấn đề: 372 chunk lá `fix` của `crm-1.0-a` do bộ duyệt tự động ghi; cần đối chiếu độc lập và sửa theo nguyên nhân gốc. Run nền: `crm-1.1-t0` (worktree) giống `crm-1.0-a` 96% theo hash + section, 348/372 chunk `fix` không đổi, 24 đổi (16 ở `f10t-operation-vi`); mọi review của `1.1-t0` đều `pending`, ảnh chưa có, bucket cũ `f54-docs`.
- Quyết định/luật (Toma xác nhận 2026-11-25): phạm vi đợt 1 là 4 bản CRM F54 + F86 (101 chunk `fix`); mức xử lý: duyệt + sửa luật + build lại, không đụng DB, không sửa `chunk_review.json` của run cũ, không commit. Quy trình: (1) dựng run mới từ raw `crm-1.0-a` + `--pdf` (code Bậc 0 đã có trên nhánh; PDF kiểm SHA256 trùng bản mới nhất trên API CRM), run id `crm-1.2-a`; (2) `build` bằng `backend\venv` (có `tiktoken`) với `--carry-review` từ `crm-1.0-a`; (3) đối chiếu từng chunk với ảnh trang (`pages/pNNN.png`), ghi verdict vào `crm-1.2-a/build/chunk_review.json` (reviewer ghi rõ là Claude, chưa người xác nhận; bản sao `.bak-before-recheck`) và nhãn chi tiết (final_verdict, severity S1–S3, root_cause, action) vào `data/ingest_runs/_summary/recheck-2026-11-25/fix_recheck.csv`; (4) gom theo nguyên nhân gốc, đề xuất luật pipeline kèm bằng chứng, **chờ Toma duyệt trước khi sửa luật**; (5) sau sửa luật build lại với `--carry-review` từ chính `crm-1.2-a` (không từ `crm-1.0-a`, tránh ghi đè verdict mới), duyệt lại chunk `pending`. Kế hoạch: [p4_crm_fix_recheck_plan_2026-11-25.md](../../reports/p4_crm_fix_recheck_plan_2026-11-25.md).
- File: dữ liệu trong `data/ingest_runs/<doc>/crm-1.2-a/` (gitignored); không đổi code.
- Kiểm chứng: `pytest tests\doc_ingest` → 423 passed. Dựng `crm-1.2-a` cho 4 bản (run 9,8 / 13,3 / 69,7 / 65,4 s; build 1–3 s): CQ không lỗi, 0 lỗi ràng buộc v2, không `asset_missing`, bucket `doc-assets`. Verdict chép: 17/17, 17/23, 136/146, 109/117; lá `fix` giữ verdict 96/101; 24 chunk `pending` mới. Số chunk tăng (298 → 303) vì build bằng venv có `tiktoken` nên bảng dài vượt 800 token bị tách (I-38); run cũ build bằng venv ingest không có `tiktoken` (token chỉ ước lượng). `f54-installation-en`: 3/3 `fix` được xác nhận với PDF: B0000 (bìa, logo F54 OCR thành “カS-”, S3), B0004 (hàng nối tiếp qua trang mất tên cổng, mô tả CN8 bị cắt; ghi chú cũ “lệch cột” sai, S2), B0005 (X47 gán CN7 thay vì CN6, Y40/CY0 gán CN4 thay vì CN5, S1).
- Phát hiện: I-56 (X47, Y40, CY0 gán sai hàng) **đã có sẵn trong raw Docling** (cell CN7 chứa “CX2 X47”, cell CN4 chứa “Y40 CY0 FG D- D+”), không phải lỗi bước chuẩn hoá; I-56b: `merge_continuation_rows` (T-15, `normalize/tables.py`) chỉ gộp hàng nối tiếp trong cùng segment (trang), hàng đầu mỗi trang không có tên cổng thành `orphan_row`.
- Mở tiếp: đề xuất luật T-15b (gộp hàng đầu trang có ô khoá rỗng vào hàng cuối segment trước của cùng bảng logic) và luật xếp lại chân theo hàng bằng `words.json` cho I-56 (chờ Toma duyệt); duyệt `f86-installation-en`, `f86-operation-en`, `f54-operation-en` và 24 chunk `pending`; `exclude_pages` bìa (manifest còn TODO); `tiktoken` cho venv ingest hoặc quy ước build bằng venv chính.

## 2026-11-25 · Tổng hợp verdict `chunk_review.json` của `crm-1.0-a` (10 tài liệu) và đối chiếu DB · loại: đánh giá

- Vấn đề: bản STATE cũ chỉ có đề xuất cho 61 chunk lỗi; Toma đã cập nhật `chunk_review.json` cho cả 10 tài liệu (ghi 2026-11-21 13:40–13:45), chưa ai tổng hợp. DB cũng chưa được đối chiếu.
- Quyết định/luật: không đổi luật hay trạng thái duyệt; chỉ tổng hợp và báo cáo. Verdict do `Codex PDF comparison` (tự động) ghi, **chưa người xác nhận**; nhóm lý do chọn thô theo từ khoá.
- File: [p4_crm_chunk_review_2026-11-21.md](../../reports/p4_crm_chunk_review_2026-11-21.md) (bảng theo tài liệu, danh sách 372 chunk lá `fix`, 24 chunk `pending`); STATE.
- Kiểm chứng: đọc 10 file `data/ingest_runs/*/crm-1.0-a/build/chunk_review.json` (gốc repo, không phải `backend/data`): 847 mục = 847 chunk, hash khớp `chunks.jsonl` (0 lệch). Chunk lá 739: **343 ok, 372 fix, 24 pending**; chunk cha 108: 47 ok, 61 fix. Nặng nhất `f10t-operation-vi` (lá: 5 ok / 100 fix); các bản Installation 3–6 fix. Đối chiếu Supabase (chỉ đọc): `doc_chunks_v2` 1.203 dòng, 1.012 lá active (364 không chặn, 62 chặn do lỗi, 586 chỉ OCR), toàn bộ `draft` và `public`; chunk CRM trong DB thuộc run `crm-1.0-a`, không phải `crm-1.1-t0`.
- Ảnh hưởng contract/API/schema: không; verdict chưa tác động `review_status` trong DB.
- Mở tiếp: sửa 372 chunk lá `fix` (phần lớn do OCR/mất nội dung ở bản Operation, gốc là I-51, I-58, I-29); xác nhận bởi người cho verdict tự động; xử lý 24 `pending`; quyết I-53; nạp lại từ run mới (`--pdf` để có ảnh).

## 2026-11-21 · `publish-assets` và bucket Storage chung `doc-assets` (D-014, giai đoạn B) · loại: thay đổi

- Vấn đề: ảnh chunk chỉ nằm local trong `normalized/images/`; `doc_chunks_v2.assets` chỉ có metadata `bucket/path`, chưa có luồng nào upload ảnh.
- Quyết định/luật (Toma 2026-11-21): một bucket **private** `doc-assets` cho mọi tài liệu (thay `<model>-docs`), đường dẫn giữ `<doc_id>/<element>.png`;
  upload **không ghi đè** (`x-upsert: false`); đường dẫn đã đẩy với nội dung khác thì dừng, đổi `doc_version`; bucket public bị từ chối; mặc định chỉ lập kế hoạch,
  `--apply` mới gọi mạng; khóa service role chỉ từ biến môi trường, không vào sổ hay log. Không đổi định dạng ảnh (không thêm dependency để nén WebP).
- File: `publish/assets.py` (kế hoạch, `StorageClient` stdlib, sổ `build/assets_published.json`), `cli.py` (`publish-assets`), 13 `manifests/*.yaml` và
  `sources/crm/manifest_draft.py` (`storage_bucket: doc-assets`); test `test_publish_assets.py` (8 test, giả Storage).
- Kiểm chứng: `pytest tests\doc_ingest` (venv ingest) → 421 passed, 1 failed có sẵn (CRLF CSV baseline). **Chưa chạy `--apply` với Supabase thật** (không có khóa trong phiên này).
- Ảnh hưởng contract/API/schema/cấu hình: manifest cũ đổi `storage_bucket`; **run đã build trước ngày này còn ghi bucket cũ trong `chunks.jsonl`, phải build lại** trước khi đẩy ảnh.
- Chưa làm / mở tiếp: các run `crm-1.1-t0` re-normalize không kèm `--pdf` nên **không có ảnh** (`asset_missing` ở mọi chunk có hình): dùng `run --raw-dir … --pdf …` để render;
  ảnh chunk thật nặng (khoảng 290 MB cho 10 tài liệu CRM, mỗi ảnh khoảng 0,16 MB; riêng catalog 654 MB) nên cân nhắc nén ở bước sau; dọn ảnh mồ côi trên Storage khi gỡ phiên bản.

## 2026-11-21 · Manifest `audience` và cột `audience` trong `doc_chunks_v2.jsonl` (D-014) · loại: thay đổi

- Vấn đề: chat cần phân biệt tài liệu công bố và tài liệu chỉ cho CRM (xem website-qa LOG 2026-11-21); chunk xuất ra chưa mang thông tin này.
- Quyết định/luật (Toma 2026-11-21): `DocManifest.audience` `public|internal`, mặc định `internal`; chunk và dòng export mang `audience`;
  13 manifest hiện có và manifest nháp sinh từ cây công khai của CRM đặt `public`; chunk catalog biên soạn (`curated`) đặt `public`.
- File: `schemas/{manifest,chunk}.py`, `build/fields.py`, `export/doc_chunks_v2.py`, `curated/build.py`, `sources/crm/manifest_draft.py`,
  13 file `manifests/*.yaml`, `chunking_loader/load_ingest_run.py` (cột mới, kiểm giá trị, bản chép v1 là `public`); test
  `test_export_v2.py`, `test_load_ingest_run.py`.
- Kiểm chứng: `pytest tests\doc_ingest` (venv ingest) → 413 passed, 1 failed có sẵn (CRLF CSV baseline).
- Ảnh hưởng contract/API/schema/cấu hình: thêm cột `audience` vào C2 (dòng export); **file `doc_chunks_v2.jsonl` đã export trước ngày này không có cột
  này nên loader từ chối** (build lại hoặc thêm cột). Chưa cập nhật `p2_chunk_contract.md` (chỉ ghi ở đây).
- Chưa làm / mở tiếp: `publish-assets` (đẩy ảnh lên bucket private, ghi sổ sha256) thuộc giai đoạn B; nạp lại 3 tài liệu thử cần cột `audience` đã áp trên DB.

## 2026-11-20 · Bậc 0: sửa luật không tốn API (I-55, I-59, I-54, I-56 nhẹ) và chạy lại 10 tài liệu · loại: thay đổi, kiểm chứng

- Vấn đề: nhóm lỗi I-54/I-55/I-56/I-59 (log kiểm duyệt bên dưới) do luật pipeline, sửa được bằng luật xác định, không cần model.
- Quyết định/luật (Toma duyệt "áp dụng bậc 0", 2026-11-20; đổi luật T-05 bước d, V-01 và S0 theo đó, chưa cập nhật p1 contract):
  S0 coi text layer `poor` (ép OCR) khi ≥ 5 mã `#` có ≥ 30% thiếu chữ số (I-55); T-20 mở rộng: cột chữ cạnh ảnh chụp màn hình trên
  trang OCR trả về thân (cờ `figure_column_released`, I-59); V-01 chuẩn hoá token (chỉ số trên `1 st`, U+FFFE, chấm dẫn mục lục) và
  lặp vượt ngưỡng chỉ là `text_duplicate` không chặn khi độ phủ đủ (I-54); header không rõ giữ làm dòng dữ liệu (không bỏ chữ), mục review
  `header_demotion_unsure` vẫn chặn chunk (I-56 nhẹ).
- File: `s0.py`, `parse/profile_probe.py`, `normalize/{figures,tables,recorder}.py`, `validate/coverage.py`, `schemas/{profile,run,normalized}.py`;
  test mới `test_tier0_rules.py`, sửa `test_coverage.py`, `test_header_classification.py`.
- Kiểm chứng: `pytest tests\doc_ingest` → 398 passed, 14 skipped, 1 failed có sẵn (CRLF CSV baseline). Chuẩn hoá lại 10 tài liệu từ raw
  cũ (run `crm-1.1-t0`) và `quality-report --crm`: chặn do lỗi **61 → 54**; mục `text_coverage_gap` **17 → 1** trang (6AVE Installation);
  6AH phục hồi Step 1–2 thủ tục 3.8.1 (có trong `chunks.html`); chunk lá 739 → 749. 0 approved vẫn như cũ.
- Ảnh hưởng contract/API/schema/cấu hình: thêm mã review `text_duplicate` (không chặn) và 4 ngưỡng `Thresholds`; không đổi SQL hay export v2.
- Chưa làm / mở tiếp: 10iV vẫn dùng raw cũ, tr.107–110 chưa ép OCR (Docling parse lại đang chạy, mới tr.20/759; cần cho I-55 ở chunk); I-57, I-58, I-56
  đầy đủ (hàng ANT, CN7+8+9), I-60 chưa sửa; chưa có CQ-14 (mã `#` hỏng), hạng rủi ro, gold set, `page-agree`; 604 chunk chỉ chặn vì OCR chưa được giải (I-53);
  chưa cập nhật p1/p2 contract.

## 2026-11-20 · Kiểm duyệt 61 chunk lỗi bằng đối chiếu PDF: nhóm lỗi và giải pháp (I-55…I-60; đính chính I-54) · loại: đánh giá, kiểm chứng

- Vấn đề: 653/739 chunk lá của 10 run CRM bị chặn; chưa rõ nguyên nhân gốc từng nhóm, nội dung chunk có đúng so với PDF không, và giải pháp.
- Quyết định/luật (Toma yêu cầu, 2026-11-20): đối chiếu từng nhóm với PDF gốc; verdict chỉ **đề xuất**, chưa ghi `chunk_review.json`; sửa luật pipeline
  chờ Toma duyệt (thứ tự đề xuất I-55 → I-59 → I-54 → I-57 → I-58 → I-56 → I-60).
- File: [p4_crm_chunk_review_2026-11-20.md](../../reports/p4_crm_chunk_review_2026-11-20.md) (nhóm lỗi, nguyên nhân, giải pháp, 21 chunk `can_sua`); sinh
  `data/ingest_runs/_summary/chunk_review_proposed.csv` (61 chunk, không commit); STATE.
- Kiểm chứng: 16/61 chunk tôi đối chiếu trực tiếp (ảnh vùng, text layer), 27 chunk do 2 agent độc lập (tôi kiểm lại F54 `B0085`, F86 `B0007` bằng text layer: đúng),
  18 chunk suy theo nhóm (cùng hash nội dung); OCR lấy mẫu 24 chunk bởi agent thứ ba (tôi kiểm lại thủ tục 3.8.1 trong `elements.jsonl`: đúng). Thử nghiệm I-55:
  `run --ocr force` tr.107–110 của 10iV (run `10iv-probe/probe-ocr-force`): mã `#` đủ ≥ 3 chữ số 223/223 (text layer gốc 2/137). Phụ lục tham số: 23 chunk
  `ambiguous_continuation` = 13 nội dung khác nhau, 5 bản chung hash.
- Ảnh hưởng contract/API/schema/cấu hình: không (chưa sửa luật nào).
- Phát hiện: I-55 text layer 10iV hỏng; I-56 bảng cổng gán sai hàng, mất hàng ANT; I-57 ảnh màn hình thành bảng; I-58 chữ trong ảnh trên trang text layer bị mất; I-59 ảnh nuốt
  chữ thủ tục (6AH, 6AVE mất Step 1–2); I-60 chunk hình gộp 9 trang. **Đính chính I-54:** mục `quality-report` bên dưới ghi "10iV tr.26–31 số đo y hệt chưa giải thích" và
  coi V-01 là suy luận chưa kiểm; nay đã giải thích: cùng một mẫu sơ đồ servo cho mỗi trục, token thiếu là nhãn hình, mục lục, chỉ số trên, ký tự hỏng; V-01 còn bỏ sót lỗi thật.
- Chưa kiểm / mở tiếp: 18 chunk chưa xem ảnh riêng; chưa xem ảnh cả 17 trang V-01; OCR mới là mẫu 24/khoảng 600 chunk; chưa sửa luật; quyết I-53 và chính sách nhãn hình
  vào `content` (chờ Toma). Run thăm dò và PDF nằm trong `data/` của worktree (gitignored).

## 2026-11-20 · `quality-report`: thống kê chunk theo trạng thái duyệt và nguyên nhân chặn (I-53, I-54) · loại: thay đổi, đánh giá

- Vấn đề: 739 chunk lá của 10 run CRM đều "bị chặn" hoặc chờ, không biết chunk nào cần xử lý trước; không có số liệu
  xuyên tài liệu về chunk đã duyệt, chờ duyệt, rủi ro; không truy được mã chặn về mục review.
- Quyết định/luật (Toma yêu cầu làm báo cáo, 2026-11-20): báo cáo chỉ đọc, không đổi hành vi duyệt hay xuất bản;
  tách "chỉ bị chặn vì OCR" (chưa kiểm chứng) khỏi "lỗi phát hiện" (bảng, hụt text); hạng rủi ro và chính sách duyệt
  mẫu **chưa làm**, chờ Toma duyệt và backtest bằng `f54/eval-c` (42 chunk fix).
- File: `report/quality_summary.py` (trạng thái chunk, nhóm nguyên nhân, `blocking_items`, V-01 trượt, md/json/csv),
  `cli.py` (`quality-report`), test `test_quality_summary.py` (8 test).
- Kiểm chứng: `pytest tests\doc_ingest` (venv ingest) → 404 passed, 1 failed có sẵn (CRLF CSV baseline); `pytest tests`
  (venv chính) → 1115 passed, 14 skipped, cùng 1 lỗi có sẵn; `check_ai_docs` đạt. Chạy thật `quality-report --crm
  --run-id crm-1.0-a`: 739 lá = 592 chặn chỉ vì OCR + 61 chặn do lỗi + 86 chờ duyệt, 0 approved; mọi mã chặn truy
  được về mục review (0 lệch).
- Ảnh hưởng contract/API/schema/cấu hình: không (chỉ thêm lệnh đọc).
- Phát hiện: I-53 — chưa có cơ chế gỡ mã chặn (`review_status` luôn `draft` khi có `review_blockers`), nên chunk OCR
  không thể `approved`; I-54 — V-01: 15/17 trang trượt chỉ vì lặp > 10% (độ phủ ≥ 91,6%), nhiều trang text layer hỏng
  (U+FFFE) hoặc là mục lục; 10iV tr.26–31 số đo y hệt chưa giải thích.
- Chưa kiểm / mở tiếp: I-54 mới là suy luận từ số đo, chưa mở từng trang; hạng rủi ro R0–R3, duyệt mẫu, đối chiếu bản
  VI/EN; chọn cơ chế cho I-53 (chờ Toma); báo cáo sinh trong `data/ingest_runs/_summary/` (gitignored).

## 2026-11-19 · crm-sync giai đoạn 1: lấy tài liệu từ CRM, chunk có vị trí trong PDF (I-51, I-52) · loại: thay đổi, quyết định, triển khai

- Vấn đề: PDF đưa tay, `doc_id`/`doc_version` gõ tay; kho tài liệu công khai của CRM không đồng bộ với kho tri thức;
  chunk chỉ trỏ được tới trang, không tới vùng trên trang hay file nguồn.
- Quyết định/luật (duyệt: Toma, 2026-11-19): khóa tài liệu là `id` CRM (`root_id` thừa); cây chỉ trả bản hiện hành;
  đổi phiên bản phát hiện bằng `version` (dạng "1.0", chỉ nhánh Bộ điều khiển) + mã file trong `file_url`; CRM
  không có sha256; không lưu URL đã ký; mỗi (model, loại tài liệu) một bản, ưu tiên EN; dừng trước làm giàu để
  duyệt nội dung trích xuất gốc; thêm `DocManifest.source` + `metadata.crm`/`metadata.locations` (contract C2 §3, §9).
- File: `sources/crm/` (`crm.yaml`, `config`, `client` (urllib), `tree`, `diff`, `lock`, `manifest_draft`,
  `commands`), `cli.py` (`crm-plan`, `crm-fetch`, `crm-status`), `schemas/manifest.py` (`CrmSource`),
  `schemas/chunk.py` (`ChunkLocation`, `locations`, `source_ref`), `build/loader.py` (kích thước trang từ `raw/`),
  `build/fields.py`, `export/doc_chunks_v2.py`, `report/chunks_report.py`, `.gitignore`; 10 manifest CRM; sổ nguồn;
  test `test_crm_sync.py`, `test_chunk_locations.py`, sửa `test_chunker.py` (cho phép manifest CRM).
- Kiểm chứng: `pytest tests\doc_ingest` (venv ingest) → 396 passed, 1 failed có sẵn (CRLF); `pytest tests` (venv
  chính) → 1098 passed trước khi sửa `test_chunker` (lỗi do manifest CRM mới), sau sửa `test_chunker.py` 31 passed.
  Chạy thật: `crm-plan` → 11 mới, 3 bỏ qua (bản VI trùng loại), 50 ngoài phạm vi; "Catalogue sản phẩm" đã bị gỡ khỏi
  cây CRM so với lúc đọc buổi sáng. `crm-fetch` → 11/11 PDF (kiểm `%PDF`, `file_size`, sha256). `run`/`build`
  `crm-1.0-a` cho 10 tài liệu → 847 chunk, CQ không lỗi, 0 lỗi xuất v2, mọi chunk có `locations` + `metadata.crm`.
- Ảnh hưởng contract/API/schema/cấu hình: C2 thêm trường tùy chọn (manifest cũ và output cũ không đổi, trừ thêm
  `metadata.locations`); không đổi SQL, loader, API chat.
- Phát hiện: I-51 bản Operation là ảnh scan (92–105 trang OCR mỗi bản; 606/847 chunk chặn `ocr_required`);
  I-52 "F54 - Operation Guide" CRM 106 trang ≠ bản V.02 171 trang đã xử lý; F86 Installation, F86 Operation,
  Hồ sơ công ty trùng sha256 file cũ; `f10t-operation-vi` OCR sai ngôn ngữ (I-29).
- Chưa kiểm / mở tiếp: chưa duyệt chunk, chưa nạp DB; giai đoạn 2 (nạp theo sổ nguồn, gỡ bản cũ, lịch chạy plan);
  run và PDF nằm trong `data/` của worktree nhánh `claude/crm-sync-phase1`.

## 2026-11-19 · Đối chiếu trạng thái với kiến trúc và code hiện tại · loại: đánh giá

- Vấn đề: `STATE.md` mốc 14/11 chưa mô tả rõ ranh giới giữa builder offline, nhánh catalog biên soạn, loader v2 và consumer truy xuất.
- Quyết định/luật: ghi riêng hai đường tạo chunk; phân biệt artifact/file draft với bước nạp `doc_chunks_v2`; giữ số liệu run gần nhất có ghi nhận và không suy diễn có run/DB mới.
- File: `STATE.md`.
- Kiểm chứng: đối chiếu `docs/ai/architecture.md`, `current-state.md`, `README.md`, `build/builder.py`, `curated/build.py` và CLI/loader.
- Ảnh hưởng contract/API/schema: không.
- Mở tiếp: hoàn tất đánh giá tra cứu offline/D-008, duyệt verdict catalog và cổng làm giàu 2c.

## 2026-11-14 · Catalog: code nhánh nguồn biên soạn + 37 chunk 7 bộ điều khiển (run `qs_catalog/curated-a`) · loại: thay đổi

- Toma duyệt nội dung 7 file + bảng chọn khớp PDF; chốt C-13 (`io_link` 6AH/6AV/10i theo bảng chọn); giữ 10iV trong
  coverage catalog; làm trọn 7 bộ điều khiển trước. Yêu cầu: **nội dung chunk bám sát nội dung PDF**.
- Dữ liệu: `verified: true` toàn bộ; chuẩn hóa về chữ in (kích thước "(mm)", nhãn "Max.Spindle…", "Max.Number…");
  thay `title` (Claude đặt) bằng `heading` in trên trang; thay `summary_highlights` bằng `summary_page` (khối "QS - <MODEL>
  CONTROLLER" trang 4–5, nguyên văn từ `elements.jsonl`); `system_package` theo khối "MODEL: …" trang 19–21; bảng chọn
  thêm `column` (tên cột in).
- Code mới `doc_ingest/curated/`: `schema.py` (Pydantic), `check.py` (`curate-check`: chữ in trên trang gồm text layer
  `raw/p{n}.words.json`, đối chiếu bảng chọn, sha256; `content_issues` kiểm từ lạ trong `content`), `build.py`
  (`curated-build`: chunk theo mục in trên trang, report `chunks.html`, `chunk_review.json`). CLI 2 lệnh mới.
- Contract C2 §15: `DraftChunk.domain` nhận 3 domain, `source` `builder|manual`, `curated_decisions`;
  `review_status` của chunk `manual` = nguồn verified + verdict `ok` (không cổng 2b/2c). SQL không đổi.
- Kết quả `curated-a` (`--doc-version 2026-11-14`): `curate-check` ĐẠT (961 chuỗi; 5 "khác thứ tự" do in xuống dòng);
  37 chunk (overview 14, spec 7, table 16), ≤ 506 token, 0 lỗi ràng buộc, 0 dòng có từ lạ; tất cả `draft` (chờ verdict).
  Loader `--dry-run`: 37 dòng, ~10k token embed ≈ 0,0002 USD.
- Registry chatbot: thêm `10S`, `10i` (website-qa LOG cùng ngày). Test: `tests/doc_ingest` 376 passed (`test_curated.py`
  10 test); `tests/chatbot` 597 passed.

## 2026-11-14 · Catalog: Bước 1 — dữ liệu biên soạn 7 bộ điều khiển + bảng chọn · loại: thay đổi

- Toma duyệt cấu trúc `curated/products/F54.yaml` và `curated/selection_matrix.yaml` (43 hàng × 7 model). Claude soạn
  tiếp `F86`, `F10T`, `10S`, `6AH`, `6AV`, `10i` từ ảnh trang 9–14, 19–21 và trang tóm tắt 4–5. Thêm `page_value`
  (giá trị in trên trang khi đã chốt khác, kèm `decision`) và `summary_highlights` (dòng chỉ có ở trang tóm tắt, vd.
  RTCP option, nút dừng khẩn cấp, phím nhôm 10i). Mọi giá trị `verified: false`.
- Kiểm chéo (script tạm, chỉ đọc): mọi giá trị `text`/`recovered` có trong chữ PDF của trang đã ghi, trừ 2 `page_value`
  mô tả gộp của 6AH (đúng dự kiến); các key trùng với bảng chọn khớp, trừ **C-13** mới: `io_link` 6AH/6AV/10i — trang
  riêng 24/16, bảng chọn theo giao tiếp 24/16 / 16/16 / 16/16 (cùng dạng C-12, chờ Toma chốt).
- Chưa có code (`curate_check`, `curated-build` làm ở bước sau khi đủ dữ liệu); chưa soạn servo, board, phụ kiện, công ty.

## 2026-11-14 · Catalog/công ty: chốt Bước 0 (C-01…C-12, mã model) · loại: quyết định

- Toma chốt: C-01 Pitch error **không có** ở F54/F86/F10T/10S (dòng gộp ở trang model là mẫu chung); C-02 6AH
  **closed loop**; C-03 6AH look-ahead **1000**; C-04 6AH encoder theo trang 6AV (trang 6AH chép mẫu F86); C-05 6AH
  torque/servo parameter theo bảng chọn; C-06 "Max. PLC Axis control" ≠ "Axis control" (2 trường; 10S: 16 trục điều
  khiển, 14 trục PLC); C-07 "Max. Spindle" ≠ "Max. Spindle Simultaneous Control" (2 trường); C-08 USB/RS485 theo bảng
  chọn (theo giao tiếp); **C-09 10S: RTCP, DWO, TWP đều tùy chọn** (bảng chọn đánh ✗ là sai); C-10 servo đến **55kW**;
  C-11 tên đúng **RBT-01**; C-12 I/O F86/F10T theo giao tiếp (bảng chọn).
- Registry: thêm mã **`10S`**, **`10i`**. Tên chuẩn model đang được CRM chuẩn hóa → **tạm** dùng "Astro 10i" làm tên
  hiển thị và alias của `10i` (bỏ khỏi alias mơ hồ của 10iV/10iVE); xem lại khi CRM chốt tên.
- Tiếp: Bước 1 — mẫu `curated/products/F54.yaml` + `curated/selection_matrix.yaml` để Toma duyệt định dạng.

## 2026-11-14 · Catalog/công ty theo hướng "nguồn biên soạn có duyệt": Bước 0 · loại: quyết định

- Toma duyệt hướng: pipeline trích chữ → dữ liệu biên soạn YAML (`doc_ingest/curated/`, `verified` từng giá trị) →
  sinh chunk `product_catalog`/`company_info` → loader v2. Là ghi đè cấp tài liệu có lý do; I-47…I-50 sửa riêng.
- Quyết định Bước 0: (1) mâu thuẫn giữa bảng chọn model và trang từng model → Claude liệt kê từng điểm (C-01…),
  Toma chốt từng giá trị; điểm chưa chốt giữ `verified: false`, không nạp. (2) Thêm model **ASTRO 10S** vào registry.
  (3) Thêm model **ASTRO 10i** (mã riêng, không gán 10iV/10iVE). (4) 6 trang lỗi font của hồ sơ công ty: Claude chép
  từ ảnh trang (`origin: image`), Toma duyệt.
- Danh sách mâu thuẫn C-01…C-12 gửi Toma trong hội thoại 2026-11-14; chờ chốt trước Bước 1.

## 2026-11-14 · Rà soát run đầu tài liệu công ty và catalog (`qs_company/20261114-084505`, `qs_catalog/20261114-090524`) · loại: phân tích

- Toma chạy `run --profile default --no-build` trên `docs/ai/doc_ingest_spike/source/QS_Company_Profile.pdf` và
  `QS_Product_Catalogue.pdf` (24 trang mỗi file, brochure thiết kế, nền ảnh toàn trang, song ngữ VI/EN). Claude đọc
  `elements.jsonl`, `tables.jsonl`, `review_queue.jsonl`, đối chiếu ảnh trang (company p4; catalog p6, p8). Không sửa code.
- **Company: chưa đạt.** 28 phần tử (28,3% ký tự chữ, trang 4, 6, 11, 13, 19, 20) bị **lỗi bảng mã font**
  ("KṩnṖ nṊṖṩḸẶ" thay "Kinh nghiệm"): ảnh trang đúng, text layer sai. S0 không bắt (`bad_char_ratio` 0 vì ký tự vẫn
  là chữ Latin hợp lệ) → **I-47**. `section_path` rỗng 308/517; 209 phần tử còn lại nằm sai dưới "7 AXES JEWELRY
  MILLING MACHINE ." (heading duy nhất được nhận vì bắt đầu bằng số) → **I-50**. Trang 7–8 (thông số 7 bộ điều
  khiển), 10 (servo), 12 (board), 14–18, 21–22 (máy, nâng cấp) sạch.
- **Catalog: chữ sạch (0% lỗi font), cấu trúc chưa đạt.** V-01 23/24 (p17 trùng 20,7%).
  - Bảng chọn model p6–p7 (`t001`, `t002`): gộp nhiều hàng vào một ô, cột lệch, tiêu đề hút cả cột; các ô ✓/✗ là
    **icon ảnh** → ma trận tính năng (bù rơ, pitch error, ATC, tool-life, torque feedback…) mất hoàn toàn → **I-49**.
  - Trang thông số từng model p8–p14: bố cục 2 cột "tên | giá trị" bị tách — tên thành list item, giá trị dồn một
    dòng ("0 - 150% Yes 500 KHz Yes Yes 1") hoặc bị **T-17 loại thành header/footer** vì lặp giữa các trang
    (33 giá trị: "Index Z", "Full axis", "250/500/1000/2000 lines"…) → mất dữ liệu → **I-48**.
  - p17 bảng mã model servo chỉ còn `figure_text` (không vào thân chunk); 3 bảng nhỏ (điện áp, công suất) đúng.
  - `section_path` rỗng toàn bộ (I-50); địa chỉ p1/p24 tách nhãn khỏi giá trị, nhãn lặp đôi.
- Nội dung nguồn cần Toma xác nhận: servo "400W~45KW" (đoạn văn) vs "400W ~ 55KW" (danh sách); ASTRO 10S chưa có
  trong registry; "ASTRO 10i" (registry 10iV/10iVE); cột "ASTRO 6AV/H" gộp 2 model; RTB-01 / RBT-01. Trùng nội dung
  giữa hai file: thông số 7 bộ điều khiển, board, servo, giới thiệu công ty.
- Chưa sang `build` (schema chunk/manifest chỉ nhận `technical_docs`).


- Toma xác nhận hướng đã thảo luận ngày 2026-11-13 trên B0074 (bảng `item | detail` của f54:p049:e013, e019). Lý do:
  bảng facts không giúp lọc (không nằm trong cột lọc nào), làm loãng vector (B0074 vượt 800 token, đẩy tóm tắt VI ra
  khỏi `embed_text`) và gây nhiễu FTS (từ lặp "cổng", "vào", "ra", "dây" kéo chunk lên ở câu không liên quan).
- Ba điểm chốt:
  1. **`embed_text` chỉ nhận câu mô tả ngắn, mỗi ảnh một câu**, có **thông tin phân biệt** (dải mã, quan hệ chính;
     vd. "…IN0–IN31 ứng với X300–X337, chung chân CX.0–CX.3 nối 24V"), không chỉ nêu loại ảnh. Câu mô tả vẫn phải
     kiểm chéo OCR (vision-trial-3 gán nhầm ảnh ở f54:p050:e002).
  2. **Bỏ fact chỉ dịch nhãn** (vd. "Output port 0 → cổng ra 0"): không có quan hệ, không có ích ở đâu.
  3. **Fact có quan hệ** (chân ↔ tín hiệu ↔ màu dây; mã tham số ↔ tên ↔ đơn vị) **để ngoài phần embed** (metadata
     hoặc `assets` của ảnh), chỉ dùng làm ngữ cảnh khi trả lời. Giữ hay không chờ đo Bước 4; muốn dùng thì website-qa
     phải nạp thêm vào ngữ cảnh (chưa có).
- Còn mở: vision có thật sự cần không — đo ở Bước 4 với 3 biến thể (A) không vision, (B) thêm câu mô tả vào
  `embed_text`, (C) thêm cả facts; bộ câu có loại chỉ trả lời được từ ảnh. Mã từ OCR vẫn đi vào `keywords` như hiện tại.
- Không đổi code. `vision-trial-3/vision_extract.py` (ngoài pipeline) vẫn xuất `facts`; khi đưa vào pipeline phải theo
  ba điểm trên.

## 2026-11-13 · I-46: scope theo nội dung (thử nghiệm sau CP-I46) (run `f54/eval-m`, `f86_italliation/eval-m`) · loại: thay đổi

- `schemas/profile.py`: `ScopeContentRule` (scope + regex tiêu đề / regex nội dung / loại chunk), `Chunking.
  scope_content_rules`, `scope_title_min_level` (mặc định 2: không xét tên phần cấp 1 như "PART 2: WIRING -
  CONNECTION - SETTING"). `build/fields.py` `_content_scopes`: scope theo manifest + loại chunk như cũ, **cộng thêm**
  scope theo nội dung (không bớt). Luật trong `profiles/default.yaml` (qs_controller kế thừa): configuration (tiêu đề
  setting/parameter/configur…; nội dung "PARAMETER screen", "user password", "parameter (status) description",
  "configure/set the parameters"), operation (chỉ dấu hiệu rõ: operating instructions, MANUAL MODE, AUTO mode, CYCLE
  START, "process (M…)", "when command M… is called"; không dùng press/screen/program), maintenance ("reports an
  error", "the cause is/of", troubleshoot), installation (loại wiring/pinout/dimension). Contract C2 §4 cập nhật.
- Test: `test_chunker.py` +1 (`test_content_scope_rules_add_but_never_remove`); `tests\doc_ingest` → 366 passed (test
  scope cũ không đổi).
- Run mới (chép `eval-l`, build + carry): F54 296/296 verdict; **chỉ scope đổi**, mọi trường khác giữ nguyên; 80
  chunk đổi (gồm cha), không chunk nào bị bớt scope; lá `configuration` 34 → 103, `installation` 152 → 153 (B0002
  bản vẽ kích thước), `operation` 91 → 92 (B0175 quy trình M100), `maintenance` 1 → 2 (B0175). F86 Installation: 0 đổi.
  Bảng so sánh: `data/retrieval_eval/scope_test/scope_diff_f54.md`, `scope_diff_f86.md`. Cần Toma xem: B0175 thêm cả
  `maintenance` (mô tả M100 có câu báo lỗi); B0234 màn hình Offset thêm `configuration` ("Set the parameters of the
  work…").
- Chưa nạp DB (cổng: Toma duyệt bảng scope).

## 2026-11-13 · CHECKPOINT CP-I46 (trước khi sửa I-46) · loại: quyết định

- Toma: gắn cờ bước hiện tại; nếu kết quả I-46 không đạt thì quay lại. Checkpoint `data/checkpoints/CP-I46/`
  (gitignore): bản sao `build/fields.py`, `schemas/profile.py`, `profiles/default.yaml`, `profiles/qs_controller.yaml`,
  `tests/doc_ingest/test_chunker.py`, contract C2, STATE doc-ingest/website-qa + `README.md` ghi trạng thái (run
  `eval-l`, DB `doc_chunks_v2` F54 296 + F86 23 draft, mốc eval `20261113-172639`, `20261113-173701-scope_test`) và
  lệnh khôi phục (chép file; nạp lại `eval-l` bằng loader).

## 2026-11-13 · Bảng thuật ngữ: electronic gear ratio = "tỷ số truyền điện tử" · loại: quyết định

- Toma: `electronic gear ratio` → `tỷ số truyền điện tử` (trước: "tỉ số bánh răng/truyền điện tử"). Bằng chứng: eval
  tra cứu Q9 "công thức tính tỷ số truyền điện tử F54" — chunk mong đợi hạng 5, vector 0,436 vì tóm tắt VI viết "tỉ
  số bánh răng điện tử" (website-qa LOG cùng ngày).
- `profiles/qs_controller.yaml`; phiên bản làm giàu đổi `v4+g1cb3720f` → `v4+g45729502`: bản ghi cũ vẫn dùng tới khi
  chạy lại `cli enrich` (sẽ làm cùng prompt v5). Chunk trong `doc_chunks_v2` chưa đổi.
- Test `tests\doc_ingest` → 365 passed.

## 2026-11-13 · Adapter `doc_chunks_v2` + loader (bước 3b, 4 của D-009) (run `f54/eval-l`, `f86_italliation/eval-l`) · loại: thay đổi

- `export/doc_chunks_v2.py`: dòng bảng `doc_chunks_v2` (§10 [p2_doc_chunks_schema_review.md](../../reports/p2_doc_chunks_schema_review.md));
  `normalize_code` (mã chung: `#`+số hoặc 1–4 chữ + số, bỏ số 0 đầu; không nhận `24V`, `GND`); `chunk_codes` (tham số
  có cấu trúc, dải trải tối đa 64 mã — dài hơn giữ hai đầu, mã I/O, nhãn hình đã xác minh, **bỏ tên model**: "F54"
  có ở 121 nhãn); `review_status` = `approved` chỉ khi cổng 2b đạt **không tạm** + verdict `ok` đúng `content_hash` +
  không có mã review chặn + (lá) làm giàu đã duyệt 2c; kiểm dòng và cả bộ (khóa trùng, `parent_key` trỏ cha).
- `build` ghi thêm `build/doc_chunks_v2.jsonl`; `chunk_quality.json` thêm `export_errors_v2`, `review_status_v2`; CLI
  in dòng "doc_chunks_v2".
- Loader mới (ngoài `doc_ingest`): `app/modules/chunking_loader/load_ingest_run.py` — `--dry-run` / `--apply
  [--embed-parents]` / `--delete --doc-id [--doc-version]`; kiểm model theo `REGISTRY["product_models"]`; embed trước
  (`OpenAIProvider.embed`, lô 100, kiểm số chiều); một transaction: xóa bản cùng (`doc_id`, `doc_version`), insert cha
  lấy `id`, gán `parent_id` cho con (sửa E-01).
- Run mới (chép từ `eval-k`/`eval-j-regress`, xóa đầu ra build cũ, build venv chính + `--labels` + carry): chunk
  giống hệt run cũ (296/296, 23/23); verdict chép 296/296 (F54), 0/23 (F86). `doc_chunks_v2`: F54 296 `draft`, F86 23
  `draft` (cổng 2b tạm → đúng quyết định), 0 lỗi ràng buộc. F54: 177 dòng có mã, 1.919 mã, nhiều nhất 120 mã/chunk
  (ảnh màn hình tham số liệt kê M1920–M1959 — nhiễu có thể có cho nhánh mã, đo ở Bước 4).
- Dry-run loader: F54 243 lá cần embed (~87,7 nghìn token ≈ 0,0018 USD; `--embed-parents` 296 dòng ≈ 0,0021 USD);
  F86 23 dòng ≈ 0,0001 USD; 0 lỗi.
- Test: `test_export_v2.py` (7), `tests/test_load_ingest_run.py` (6). Từ `backend/`: `..\.venv-ingest\Scripts\python.exe
  -m pytest tests\doc_ingest` → 365 passed; `.\venv\Scripts\python.exe -m pytest tests` → 1068 passed, 14 skipped.
- Chưa ghi DB (Cổng 2).

## 2026-11-13 · Chuẩn bị chạy thử thật trên Supabase: đánh giá lại `doc_chunks` (Bước 5 sơ bộ) · loại: phân tích

- Kế hoạch đã duyệt: kiểm Supabase (chỉ đọc) → tài liệu đánh giá schema → Toma duyệt → SQL v2 + adapter → loader →
  `evals/run_retrieval_eval.py` trên DB thật → website-qa dùng v2. Đã làm tới bước tài liệu đánh giá, dừng chờ duyệt.
- Bằng chứng mới cho thiết kế khóa: giữa `eval-h` và `eval-k`, 0/294 chunk giữ `chunk_key`, 294/296 khớp
  (`content_hash`, `section_path`) → `chunk_key` chỉ là khóa trong một phiên bản; nhãn đánh giá dùng cặp hash + path.
- Đề xuất: [p2_doc_chunks_schema_review.md](../../reports/p2_doc_chunks_schema_review.md) (cột `doc_version`,
  `chunk_role`, `codes` trải dải, `printed_page_*`, `embedding_model`, `source`, `review_status`; bỏ check model cứng,
  loader kiểm theo registry; cha không bắt buộc embedding). Hiện trạng DB và lệch repo: website-qa LOG cùng ngày.
- Không đổi code `doc_ingest`.

## 2026-11-13 · Đóng cổng 2c của làm giàu v4: không đạt (run `f54/eval-k`) · loại: quyết định

- Toma đóng verdict (b) của mẫu 2c (30 chunk) mà không chấm từng chunk. Cổng 2c của phiên bản `v4+g1cb3720f`:
  **không đạt** — Claude đề xuất 17 ok / 13 fix, có 2 lỗi nặng (B0040 "trục chính", B0287 "bù trục chính": nội dung
  không có trong chunk). Các nhóm lỗi: câu hỏi không trả lời được (chunk chỉ liệt kê mã, chunk danh mục, chunk chỉ có
  hình), đoán trên chunk mỏng, thuật ngữ (homing switch, soft limit, board, workpiece homing).
- `chunk_review.json` không ghi verdict làm giàu cho mẫu này (30 chunk vẫn `pending`, hết hạn khi đổi phiên bản).
  Mẫu 2c mới chọn sau prompt v5 + bảng thuật ngữ bổ sung, và sau quyết định hướng ảnh (vision) theo Bước 4.
- Không đổi code.

## 2026-11-13 · Định nghĩa phạm vi: luồng chung cho mọi PDF upload, F54 là thí điểm · loại: quyết định

- Toma: luồng chunking không chuyên biệt cho F54; được triển khai để phân tích, xử lý và tạo chunk cho các PDF được
  upload. F54 là bản áp dụng đầu để phát hiện, khắc phục lỗi mới và chuẩn hóa luồng cho các PDF sau.
- Ghi vào README mục Phạm vi kèm nguyên tắc: sửa bằng luật chung; phần phụ thuộc hãng/dòng tài liệu đặt ở profile;
  ghi đè riêng tài liệu chỉ qua manifest có lý do; lỗi mới ghi dạng lỗi (I-xx) + test + hồi quy F86; đánh giá ngưỡng,
  cổng, chi phí theo cả lô.
- Áp vào việc đang làm: luật tầng 1 phân nhóm ảnh (`vision-trial-3/classify_figs.py`) đang chứa giá trị riêng QS/F54
  (watermark "QS TECHNOLOGY", phím máy, từ màn hình JOG/READY, phần mềm DNC Explorer) → khi đưa vào pipeline phải
  chuyển sang profile; luật chung chỉ gồm tín hiệu không phụ thuộc hãng (OCR có/không chữ, khung đỏ, mật độ mã, loại
  chunk). Ghi đè thủ công trước đây (`exclude_pages: [1, 2]` của F54) vẫn đúng nguyên tắc (manifest + lý do).
- Không đổi code. Ảnh hưởng: các đề xuất sau (vision, cổng 2c, Bước 4) đánh giá cả trên F86, không chỉ F54.

## 2026-11-13 · Thử vision theo nhóm ảnh: tầng 1 (luật) + tầng 2 (LLM xếp nhóm) + kiểm chéo OCR, 14 chunk · loại: thử nghiệm

- Toma chốt quy trình 3 tầng: tầng 1 luật tự động gán nhóm; ảnh "chưa rõ" → tầng 2 (gpt-4.1-mini tự xếp nhóm trong
  cùng lần gọi trích); tầng 3 Toma duyệt. Script ngoài pipeline (không sửa code); kết quả, script và báo cáo duyệt:
  `data/ingest_runs/f54/vision-trial-3/` (`fig_groups.json`, `extract.json`, `report.md`).
- Tầng 1 (`classify_figs.py`, `.venv-ingest`: Pillow/numpy có sẵn): tín hiệu = OCR thô đã bỏ watermark/rác, khung đỏ
  (màu điểm ảnh), loại chunk. 208 ảnh lá: **192 tầng 1**, **13 tầng 2**, **3 không gửi** (B0080 đầu cáp, B0275 QR,
  B0281 logo). Nhóm: đấu dây 71, tham số 35 (gồm màn hình bit +0..+7), trình tự 5, giản đồ xung 5 (mới, B0109), mặt máy
  khoanh 4, thao tác/PLC/phần mềm PC 70, mặt máy 1, kích thước 1. Khung đỏ 113/208.
- Trích (`vision_extract.py`): quy tắc riêng theo nhóm, output `images[{group, facts[{item, detail}], desc_vi}]` + tóm
  tắt/câu hỏi/từ khóa; 14 chunk (8 Toma chọn + B0011, B0020, B0177, B0002, B0003, B0112), 27 ảnh; 79.452 + 8.198
  token ≈ **0,045 USD**. Kiểm chéo OCR: unverified (mã model viết, OCR không có), missing (mã OCR có, model bỏ; nhóm
  1–3), value_leak (giá trị màn hình lọt vào; nhóm 2, 4, 5).
- Claude đối chiếu ảnh gốc, đề xuất 10 ok / 4 fix: **B0074** gán nhầm thứ tự 5 ảnh, bỏ sót cả ảnh OUTPUT (Y300–Y337)
  — kiểm OCR bắt được (độ phủ 0,05, 32 mã unverified); **B0109** diễn giải sai sóng Pul/Dir chiều âm; **B0002** số đúng
  nhưng đoán sai "đo cái gì"; B0196 sai thuật ngữ ("về home chi tiết gia công"). Đúng quy tắc: B0050 ghép đủ 14 chân ↔
  màu dây; B0149/B0161/B0204 không ghi giá trị màn hình; B0147 đọc đúng 3 giai đoạn (OCR đọc hỏng → 2 unverified giả).
  Tầng 2: B0003, B0112, ảnh Shift+7 của B0196 → `8_khac`, hợp lý.
- Phát hiện phụ: B0011 có 2 ảnh trùng nhau, B0109 có ảnh lặp (trùng hình chưa bị loại ở chuẩn hóa); ảnh I/O link ghi
  IN24(X320)… (lỗi in PDF, đúng ra X330); ảnh B0275 `e005` chỉ có mẩu watermark "QLOGY" → nên vào danh sách bỏ.
- Bài học cho thiết kế: ảnh dày (nhóm 1, 2) nên gọi **mỗi ảnh một lần** (chunk 5 ảnh làm lệch thứ tự); nhóm 7 chỉ ghi
  số, không đoán chiều đo; "unverified" nghĩa là cần người xem, không phải chắc chắn sai.
- Không đổi contract/schema/code pipeline. Chờ Toma duyệt 14 chunk (`report.md`, tầng 3). Verdict mẫu 2c vẫn tạm giữ.

## 2026-11-13 · Phân tích nhóm ảnh cho làm giàu vision + luật lọc theo OCR (run `f54/eval-k`) · loại: phân tích

- Chỉ đọc dữ liệu (`chunks.jsonl`, `figure_ocr.jsonl`, ảnh gốc); không sửa code, không gọi LLM. Verdict mẫu 2c vẫn tạm giữ.
- Toma phân nhóm ảnh khi xem các chunk; Claude đối chiếu ảnh B0147, B0149, B0161, B0177, B0196, B0204. Nhóm và đề xuất:
  (1) sơ đồ đấu dây/mạch — gửi, trích đủ cặp chân ↔ tín hiệu ↔ màu dây; (2) màn hình bảng tham số (B0149, B0086,
  B0193) — lấy mã, tên, **đơn vị** (B0149: "mm/min" chỉ có trong ảnh), KHÔNG lấy giá trị đang hiển thị (2000, 16576…
  là giá trị máy mẫu); (3) sơ đồ chuyển động/trình tự — B0147 có tham số từng giai đoạn về home, B0177 chỉ mũi tên
  (9)(10); (4) ảnh mặt trước có khoanh đỏ (B0196) — chỉ mô tả vùng khoanh; (5) màn hình thao tác/PLC (B0161 là màn
  hình PLC Ladder + tham số, không phải sơ đồ mạch; B0204) — chỉ tên màn hình/nút được khoanh; (6) ảnh trang trí — bỏ.
- Câu hỏi "LLM có mô tả hết giá trị trong ảnh": không (B0074 bỏ IN0=X300…, B0050 không ghép màu dây với chân; giới hạn
  600 ký tự) và không nên với giá trị minh họa — B0204 chứa tọa độ, giờ, đường dẫn file mẫu (nhiễu). Giá trị có tính
  quy định nên trích có cấu trúc (vd. trường `figure_facts`), kiểm chéo với nhãn OCR.
- Phát hiện phụ: ảnh B0147 ghi "#12110 → #12113" (Homing Feedrate 3rd) → xác nhận #12103 ở B0159 là lỗi in (I-40d).
  Ảnh B0204 (chunk ghi chú) minh họa các bước nằm ở chunk anh em B0205; ảnh bị cắt mất cột "Instructions".
- Luật Toma đề xuất "OCR không ra chữ/số → ảnh trang trí, không gửi vision": 208/208 ảnh lá đã OCR; chỉ **3/208** rỗng
  sau khi bỏ watermark — B0281 logo (đúng), B0080 ảnh đầu cáp giắc DB (có ích), B0275 **mã QR** (chứa link, OCR không
  đọc được). Ảnh "chỉ có máy" vẫn có chữ (B0001: nhãn phím, tên cổng CN9/CN8…; B0002 là bản vẽ kích thước) → luật an
  toàn nhưng lọc rất ít. Rủi ro: bỏ nhầm ảnh linh kiện/QR/khung đỏ không chữ; watermark và chữ rác OCR ("bobobbo",
  "日") làm ảnh trang trí bị tính có chữ; phải dùng OCR thô, không dùng `figure_labels` (chỉ giữ nhãn dạng mã).
- Đề xuất (chưa làm): giữ luật làm bộ lọc đầu, có ngoại lệ (chunk `wiring`/`dimension`/`pinout`, ảnh có khung đỏ, mã
  QR → ghi link ở manifest) và liệt kê ảnh bị bỏ để duyệt; ghi "không làm giàu bằng ảnh", không gán "trang trí".
- Mở tiếp: gán nhóm ảnh + quy tắc lấy gì theo nhóm → thử gpt-4.1-mini ~12 ảnh (2/nhóm) → quyết định hướng C (đổi C2 §8,
  schema) → chọn lại mẫu 2c; sửa bảng thuật ngữ (homing switch, soft limit, board, workpiece homing).

## 2026-11-13 · Thử vision với gpt-4.1-mini trên cùng 8 mẫu (so với gpt-4o-mini) · loại: thử nghiệm

- Cùng script, prompt, ảnh và 8 chunk như `vision-trial-1`; chỉ đổi model (env `TRIAL_MODEL`, giá 0,40/1,60 USD/1M).
  Kết quả: `data/ingest_runs/f54/vision-trial-2/`. Verdict mẫu 2c vẫn tạm giữ.
- Chi phí: 43.203 + 2.502 token ≈ **0,021 USD** (gpt-4o-mini: 0,062) — ảnh chỉ ~2–5k token; ước toàn F54 (208 ảnh)
  ≈ 0,37 USD. Thời gian 28 s (gpt-4o-mini 40 s). Mô tả dài hơn ~1,5 lần.
- Đối chiếu tay với ảnh gốc: 8/8 không bịa trong `figure_desc_vi`; chi tiết hơn gpt-4o-mini ở B0003 (cả cây menu con),
  B0050 (đọc được màu dây — gpt-4o-mini bỏ), B0074 (mô tả từng ảnh: RS485 CN4↔CN10 FG/D−/D+, LOW/HIGH INPUT, OUT0–OUT7
  mỗi cổng, 24V/0V), B0086 (AX5–8.ENA = 0), B0193 (M1950 ở 02024 cột +6, dải 0~255). Gọi "công tắc homing" thay vì
  "công tắc hành trình". Còn yếu: B0050 liệt kê màu dây theo thứ tự chứ không ghép từng chân; B0074 không nêu
  IN0=X300…/OUT0=Y300…; B0193 câu hỏi "M1950 nên đặt trong khoảng nào" suy từ dải 0~255 của màn hình; một số câu hỏi
  không trả lời được (B0003 "tạo và mở file", B0193 "kích hoạt workpiece homing"); từ khóa VI có tiếng Anh/mã
  (optocoupler, RS485, M1950).
- Kết luận đề xuất: gpt-4.1-mini tốt hơn và rẻ hơn ~3 lần cho phần ảnh. Không đổi contract/schema/code pipeline.

## 2026-11-13 · Thử nghiệm hướng C: làm giàu chunk hình bằng model vision (8 mẫu) · loại: thử nghiệm

- Bối cảnh: duyệt mẫu 2c (Claude đề xuất 17 ok / 13 fix, 2 lỗi nặng; Toma chọn tạm giữ verdict) cho thấy lỗi tập trung ở
  chunk hình: làm giàu chỉ nhận chữ của chunk (tiêu đề + caption), không nhận ảnh hay nhãn OCR → đoán (B0040 "trục
  chính", B0011 "cảm biến"). Toma yêu cầu thử gửi ảnh cho model vision với 8 mẫu.
- Cách làm: script ngoài pipeline (không sửa code, không ghi `eval-k`): system prompt v4 + thuật ngữ + phần thêm cho ảnh,
  trả thêm `figure_desc_vi`; gpt-4o-mini, `detail: high`, ảnh `original.png` của mọi asset. Mẫu: B0003, B0011, B0019,
  B0040, B0050, B0074, B0086, B0193 (12 ảnh). Kết quả và script: `data/ingest_runs/f54/vision-trial-1/`.
- Chi phí: 405.040 + 1.849 token ≈ **0,062 USD** cho 8 chunk (≈ 34k token/ảnh; gpt-4o-mini tính ảnh rất đắt). Ước
  toàn F54 (136 lá có ảnh, 208 ảnh): ≈ 1,1 USD, gấp ~19 lần làm giàu chữ (0,057 USD).
- Đối chiếu tay với ảnh gốc: `figure_desc_vi` **không bịa** ở 8/8; đúng chi tiết ở B0003 (9 menu), B0011 (X40–X47/CN6,
  X50–X57/CN7, 3K, 24V, CX.0–CX.3), B0019 (NPN COM 24V, PNP COM 0V, X40–X43 = trục X–A), B0040 (Alarm+/24V, X51–X54 =
  trục X–A — sửa được lỗi nặng của v4), B0086 (AX1–4.ENA = 1), B0193 (M1920–M1959, M1950 khung đỏ).
- Còn yếu: mô tả hời hợt khi nhiều ảnh/ảnh dày (B0050 bỏ màu dây; B0074 5 ảnh chỉ nêu cổng 0–3, bỏ IN0=X300…, CN4↔CN10
  D+/D−); B0193 hỏi "giá trị mặc định M1950" từ giá trị đang hiển thị (suy diễn); một số câu hỏi vẫn không trả lời được;
  thuật ngữ chưa sửa (homing switch → "công tắc hành trình", board → "bảng"); từ khóa VI chứa mã (M1950, X40).
- Không đổi contract/schema/code pipeline. Mở tiếp: Toma quyết định có đưa vision vào Bước 3 (trường riêng
  `figure_desc_vi` + duyệt riêng) và thử model rẻ ảnh hơn (gpt-4.1-mini) trước khi chạy toàn F54.

## 2026-11-13 · Bước 3: làm giàu toàn bộ F54 + cổng 2c (mẫu duyệt tay) (run `f54/eval-k`) · loại: thay đổi

- Toma sửa bảng thuật ngữ (`qs_controller.yaml`, 22 thuật ngữ; vd. tool setter → bộ so dao, homing → về home/về 0,
  backlash → bù rơ cơ khí; JOG, PLC giữ tiếng Anh) → phiên bản làm giàu `v4+g1cb3720f`.
- Làm giàu toàn bộ F54 (`cli enrich`, gpt-4o-mini): 199 nội dung, 0 lỗi, 244.804 + 23.869 token ≈ **0,051 USD**.
- **Lỗi thiết kế phát hiện qua CQ-13** (13 chunk "mã lạ G00"): làm giàu khóa theo `content_hash` nên thủ tục lặp nguyên
  văn ở 13 mục tham số (I-40c) dùng chung tóm tắt viết cho mục "JOG RAPID (G00)" — sai với 12 mục. Sửa: khóa =
  (`content_hash`, `section_path`) (`EnrichmentRecord.section_path`, `loader.enrichment_key`); bổ sung `section_path`
  cho 295 bản ghi cũ từ `chunks.jsonl` (290 duy nhất, 4 theo `chunk_key`, 1 không xác định → không dùng); làm giàu thêm
  24 chunk trùng nội dung ở mục khác (0,0061 USD). Tổng làm giàu F54 ≈ 0,057 USD; cả Bước 3 tới giờ ≈ 0,075 USD.
- Cổng 2c (C2 §10): `ChunkReviewEntry` thêm `enrichment_verdict/note/version/severe`; `enrich/review.py` (chọn mẫu,
  đếm verdict còn hiệu lực, `gate_2c`: 0 chờ, 0 lỗi nặng, ≥ 90% ok); `cli enrich-sample`, `cli enrich-approve` →
  `build/enrichment_approval.json` → `approved`; `chunk_quality.json.enrichment` thêm `auto_passed`, mẫu, `versions`;
  trang duyệt có mục cổng 2c và lọc `mau_2c`; chép verdict làm giàu khi `--carry-review`.
- Lệch kế hoạch: phê duyệt ghi file riêng `enrichment_approval.json` thay vì sửa `enrichment.jsonl` (giữ append-only).
- Kết quả `eval-k`: 243/243 lá làm giàu; tự động 2c **ĐẠT** (0 mã lạ, 1 bớt câu hỏi/từ khóa, 0 cắt content); mẫu 30
  chunk (1 chunk có cờ `glossary_term_missing`: B0161 Soft Limit + 29 phân tầng) chờ Toma duyệt.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 358 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1055 passed, 14 skipped. Test mới: trùng nội dung khác mục, cổng 2c.
- Ảnh hưởng contract/API/schema: C2 §10 (cổng 2c); schema review/enrichment như trên. Không ghi database.
- Mở tiếp: Toma duyệt 30 mẫu → `enrich-approve` → Bước 4.

## 2026-11-13 · Bước 3: prompt v3 → v4, thí điểm lại 19 chunk (run `f54/eval-k`) · loại: thay đổi

- Quyết định (Toma, phương án 2): sửa tiếp 2 lỗi còn lại của v2 trước khi chạy toàn bộ.
- v3: câu hỏi về tài liệu/hình bị bỏ khi còn ≥ 2 câu (`is_meta_question`), còn lại thì cờ `faq_meta`; thuật ngữ bảng
  ghi "giữ tiếng Anh" có trong content phải có nguyên văn trong làm giàu, thiếu → cờ `glossary_term_missing`; prompt
  thêm ví dụ câu hỏi cho đoạn chỉ có hình. Chạy 19 chunk (0,0050 USD): hết câu hỏi về hình, B0186 có "backlash", 0 cờ.
  **Lỗi do v3 gây ra:** B0001 (ảnh mặt trước/sau) có câu hỏi "Kích thước F54 bao nhiêu?" chép từ ví dụ trong prompt
  (không trả lời được từ đoạn); B0001 mất hết từ khóa VI vì bước dọn coi tên model `F54` là mã.
- v4 (sửa lỗi của v3): bỏ ví dụ cụ thể, thay bằng "hỏi điều chính hình cho biết theo tiêu đề/caption"; cấm "trong tài
  liệu", "trong phần này", "được trình bày"; `faq_meta` bắt thêm "phần này/mục này"; từ khóa VI được giữ tên model.
  Chạy 19 chunk (`v4+ga40bffb5`): 19/19, 0 lỗi, 0 cờ, 24.010 + 2.395 token ≈ **0,0050 USD**; sau build 0 mã lạ, 0 bớt,
  0 cắt content, lá lớn nhất 676 token. B0001 có từ khóa và câu hỏi đúng ảnh; hết "trong tài liệu". Còn sót nhẹ
  (để duyệt mẫu 2c): B0048 "được trình bày rõ ràng", B0022 câu hỏi tối nghĩa, vài từ khóa chung ("hướng dẫn sử dụng").
- `enrichment.jsonl` của `eval-k` giữ đủ v1…v4 cho 19 chunk (so sánh); build dùng bản mới nhất. Tổng chi phí thí điểm
  Bước 3 tới giờ ≈ 0,018 USD.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 356 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1053 passed, 14 skipped.
- Mở tiếp: Toma duyệt v4 → chạy phần còn lại (~224 nội dung, ≈ 0,06 USD) → duyệt mẫu 2c.

## 2026-11-13 · Bước 3: prompt v2 + bảng thuật ngữ, thí điểm lại 19 chunk (run `f54/eval-k`) · loại: thay đổi

- Quyết định (Toma): bảng thuật ngữ bổ sung dần trong quá trình cập nhật luồng (team kỹ thuật/khách hàng bận); bắt
  đầu bằng bản nháp, thuật ngữ chưa chắc giữ tiếng Anh.
- Code: `Profile.glossary` (`GlossaryTerm en/vi/note`), bản nháp 22 thuật ngữ trong `profiles/qs_controller.yaml`
  (16 có cách gọi VI; PLC, macro giữ tiếng Anh; tool setter, homing, backlash, offset chờ team xác nhận); prompt v2
  (`enrich/prompt.py`: không mở "Đoạn này…", không hỏi về tài liệu/hình, từ khóa VI không mã/tiếng Anh, chèn bảng
  thuật ngữ); `prompt_version` = `v2+g<dấu bảng>` → sửa bảng là `enrich` làm lại; `--only-enriched`; `clean_output` bỏ
  từ khóa VI chứa mã; cờ kiểm `summary_preamble`. Test `test_enrich.py` +3.
- Run `f54/eval-k` (chép `normalized/`, `figure_ocr.jsonl`, `enrichment.jsonl` từ `eval-j`, build venv chính, carry
  296/296): chunk không đổi. `enrich --only-enriched` (prompt `v2+ga40bffb5`): 19/19 ghi, 0 lỗi, 0 cờ; thật 21.084 +
  2.304 token ≈ **0,0045 USD**; sau build: 0 mã lạ, 0 bớt, 0 cắt content, lá lớn nhất 633 token.
- So v1 ↔ v2 (cùng 19 chunk; file `enrichment.jsonl` giữ cả hai phiên bản): hết "Đoạn này" (19/19); thuật ngữ áp đúng
  ("tool setter", "rơ-le trung gian", "chạy tay (JOG)", "tưới nguội"); hết mã trong từ khóa VI; câu hỏi về tài liệu/hình
  giảm, còn 2 (B0001 "Hình ảnh… tìm ở đâu?", B0002 "Có hình vẽ nào…?"); B0186 dịch backlash thành "bù trục" và mất từ
  "backlash" dù bảng ghi giữ tiếng Anh; vài từ khóa chung ("điều khiển CNC", "hướng dẫn sử dụng").
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 355 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1052 passed, 14 skipped.
- Ảnh hưởng contract/API/schema: C2 §8 (bảng thuật ngữ, phiên bản làm giàu); profile thêm `glossary`. Không ghi
  database.
- Mở tiếp: Toma duyệt v2 → chạy phần còn lại (~224 nội dung, ≈ 0,06 USD) → duyệt mẫu 2c; bổ sung thuật ngữ dần.

## 2026-11-13 · Duyệt gộp ghi chú vào chunk hình (B0006, B0060) — mốc so sánh cho Bước 4 · loại: quyết định

- Duyệt: Toma, `ok` cho 2 chunk gộp theo R-13 (I-45) của `f54/eval-j`; reviewer `toma+claude`. F54 `eval-j`: 296 ok /
  0 fix / 0 chờ, **cổng 2b đạt (tạm)**.
- Ghi để so lại khi kiểm tra cứu (Bước 4) — trước (`f54/eval-i`) / sau (`f54/eval-j`):

  | Mục | Trước | Sau |
  |---|---|---|
  | 2.2 Controller power supply | cha B0007 (97 token) = con B0008 figure (Figure 6, 67 token) + con B0009 overview ("Note:" 2 dòng, 83 token) | B0006 standalone figure (97 token): Figure 6 + Note |
  | 2.4.1 Y40 output signal (S-ON) | cha B0063 (272 token) = con B0064 wiring (Figure 46, 47; 253 token) + con B0065 overview ("Note: Ter.(5,9,13,14)…", 96 token) | B0060 standalone wiring (272 token): sơ đồ + Note |

- Giả thuyết cần đo: chunk gộp khớp tốt hơn câu hỏi về ghi chú (vd. "nguồn xung hay biến áp cho F54?", "chân FG dùng
  làm gì?", "Ter.5,9,13,14 là gì?") vì ghi chú nằm cùng ngữ cảnh hình; rủi ro: vector của chunk hình loãng hơn. Bước 4
  thêm các câu hỏi này vào bộ đánh giá; nếu kém hơn thì nới/tắt R-13 (`figure_text_max` hoặc bỏ gộp).
- Phần 6 trong câu hỏi trước của Toma: không có (ghi dư).

## 2026-11-13 · Loại chunk theo manifest, bỏ ảnh khung chữ, giới hạn nhãn OCR, gộp ghi chú vào hình (run `f54/eval-j`) · loại: thay đổi

- Vấn đề (Toma đánh giá chunk thử trên `eval-i`): chưa có cách loại chunk vô ích (B0000: bìa + lời cảm ơn, trang
  1–2); 22 ảnh khung "Instructions" (`text_frame`) vẫn là asset dù chữ đã ở `content`; nhãn OCR ảnh tổng quan (B0002:
  34 mã chân) vào từ khóa; hình + ghi chú ngắn bị tách vụn (B0007 → B0008 67 + B0009 83 token).
- Quyết định (duyệt: Toma, chọn từng mục): (1) manifest `exclude_pages`/`exclude_sections`/`exclude_reason`, lý do độ
  phủ `manifest_excluded`; F54 loại trang 1–2; (2) hình `text_frame` không là asset, không làm khối thành chunk hình
  (I-44); T-20 nhận khung có tiêu đề khung mà chỉ còn caption bước (F54 trang 153 từng bị sót); (3) nhãn OCR chỉ vào
  từ khóa của chunk `wiring`/`pinout`/`dimension` (`chunking.figure_label_keyword_types`); (4) ghi chú ngắn ngay sau
  chunk hình cùng mục gộp vào chunk hình khi tổng ≤ 600 ký tự (C2 R-13, I-45).
- Lệch kế hoạch: luật gộp ghi đánh số R-13 (kế hoạch ghi R-14; R-13 chưa dùng vì phương án tách cửa sổ cha của I-43
  bị bỏ). Ngoài 2.2, mục 2.4.1 cũng được gộp.
- File: `schemas/{manifest,profile}.py`, `manifests/f54.yaml`, `build/{chunker,fields,builder}.py`,
  `normalize/figures.py`; test `test_chunker.py` (+3, sửa 1), `test_text_frames.py` (+1); C1 T-20; C2 §3, §7, §8.1,
  R-13; [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.16;
  [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md) (I-44, I-45).
- Kiểm chứng: `f54/eval-j` (chuẩn hóa lại từ raw `eval-i` vì T-20 đổi, build venv chính, carry từ `eval-i`, chép
  `figure_ocr.jsonl` + `enrichment.jsonl`): 296 chunk (cha 53, con 150, độc lập 93; trước 301); chỉ 3 mục đổi nội
  dung (B0000 loại — 9 phần tử `manifest_excluded`; 2.2 → 1 chunk hình; 2.4.1 → 1 chunk wiring); asset lá 234 → 208
  (23 khung chữ + 3 ảnh bìa); 74 lá chỉ đổi từ khóa; CQ-01…CQ-12, độ phủ 1,0, ranh giới P/R 1,0; review 294 ok /
  2 pending; làm giàu 19/243 lá còn khớp (bản ghi B0000 không còn dùng). Hồi quy `eval-j-regress`: F86 Installation,
  Operation 0 chunk/asset đổi; 1 và 5 chunk đổi từ khóa (bỏ nhãn OCR trên chunk không phải wiring/pinout/dimension).
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 352 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1049 passed, 14 skipped.
- Ảnh hưởng contract/API/schema: C1 T-20; C2 §3 (manifest), §7, §8.1, R-13; `DocManifest` thêm 3 trường; profile thêm
  `figure_label_keyword_types`. Trả ảnh kèm câu trả lời (vd. bản vẽ kích thước B0003) còn phụ thuộc website-qa (chưa
  có SSE ảnh) và bước xuất bản (upload asset). Không ghi database.
- Mở tiếp: Toma duyệt 2 chunk mới (B0006, B0060); câu hỏi phần 6 của Toma bị cắt; prompt v2 + thuật ngữ.

## 2026-11-13 · Bước 3: code làm giàu tiếng Việt + thí điểm 20 chunk (run `f54/eval-i`) · loại: thay đổi

- Quyết định (Toma, theo kế hoạch Bước 3): chạy với cổng 2b đạt **tạm** (nhãn `verified: false`); model
  `gpt-4o-mini` (truyền `--model`, vì env `OPENAI_MODEL` của dịch vụ chat là `gpt-4.1-mini`); thí điểm 20 chunk phân
  tầng trước khi chạy hết.
- Code: module `enrich/` (`checks`, `prompt` v1, `client` OpenAI structured output, `runner`, `env`); lệnh
  `cli enrich` (`--sample`, `--limit`, `--dry-run`, `--model`, giá); `build` đọc `build/enrichment.jsonl` theo
  `content_hash`, ghép tóm tắt/câu hỏi/từ khóa VI vào `embed_text` chunk lá, `enrichment_status = draft`, không bao
  giờ cắt `content` vì làm giàu (bớt câu hỏi → từ khóa → tóm tắt, cờ `enrich_trimmed`); kiểm 2c (CQ-13) trong
  `chunk_quality.json.enrichment`; trang duyệt hiện tóm tắt/câu hỏi. Schema: `EnrichmentOutput`, `EnrichmentRecord`,
  `EnrichmentSummary`.
- Lệch kế hoạch: (1) `doc_ingest` không được import `app.core.config` (`test_import_boundary.py`) → key/model đọc từ
  env, rơi về `backend/.env` qua `python-dotenv` (có sẵn); giá gpt-4o-mini là hằng số, model khác phải truyền giá.
  (2) Bảng bước của `pipeline.py` dành tên module `enrich` cho trích fact → đổi bước fact sang module `facts`, thêm
  bước "Làm giàu tiếng Việt". (3) Luật mã lạ ban đầu bắt nhầm tên model `F54` (6/20) → so với `content` + model +
  section path; đã tính lại `checks` của 20 bản ghi (không gọi lại API).
- Run `f54/eval-i` (chép `normalized/` từ `eval-h`, build venv chính, carry 301/301): chunk không đổi so với `eval-h`.
  Dry-run toàn bộ: **221** nội dung khác nhau cần làm giàu (246 lá; 25 lá trùng nội dung với lá khác), ước tính
  177K + 55K token ≈ 0,060 USD.
- Thí điểm (`--sample 20`, 8 loại chunk): 20/20 ghi, 0 lỗi; thật 15.223 + 2.294 token ≈ **0,0037 USD**; sau build: 0 mã
  lạ, 0 bớt, 0 cắt content; token lá tăng ~+150–210 (lớn nhất B0182 480 → 667 ≤ 800). Cổng 2c: 20/246 (chưa đạt —
  đúng, chưa chạy hết).
- Nhận xét chất lượng thí điểm (chờ Toma duyệt): tiếng Việt tự nhiên, giữ nguyên mã (`M1920`, `#14006`, `Y44`); nhưng
  (a) hầu hết tóm tắt mở bằng "Đoạn này …" (thừa); (b) vài câu hỏi hỏi về tài liệu/hình, không trả lời được từ nội
  dung (B0002, B0003, B0029 "Mô hình nào…"); (c) từ khóa VI có lẫn mã/tiếng Anh ("tham số M1920", "dimension",
  "MPG"); (d) thuật ngữ dịch chưa theo cách gọi ở VN ("bộ định vị công cụ" cho tool setter, "bù trừ độ trễ" cho
  backlash) → đề xuất prompt v2 + bảng thuật ngữ.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 348 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1045 passed, 14 skipped. Test mới `test_enrich.py` (client giả).
- Ảnh hưởng contract/API/schema: C2 §3 (lệnh), §8 (làm giàu), §10 (cổng 2c, chạy với cổng tạm). Không ghi database.
- Mở tiếp: Toma duyệt thí điểm → prompt v2 (+ thuật ngữ) → chạy lại 20 thí điểm → chạy 201 còn lại.

## 2026-11-13 · Làm rõ D-008: Bước 3 và embed chỉ cho chunk lá · loại: quyết định

- Câu hỏi (Toma): theo D-008 thì chunk cha không được tìm; vậy làm giàu tiếng Việt (Bước 3) và embed có chỉ làm
  cho chunk con và độc lập không? Trả lời: đúng (duyệt: Toma).
- Căn cứ, kiểm trên `f54/eval-h` (chỉ đọc): 55 cha, 154 con, 92 độc lập; `content` con nằm trong cha 154/154;
  `content` cha = nối nguyên văn các con 55/55 (2–5 con mỗi cha); 0 phần tử chỉ có ở cha; tập chunk lá (246) phủ
  toàn bộ nội dung. 5 phần tử nằm ở > 1 chunk lá đều là segment bảng trang 167–171 (một segment trang chứa dòng của
  2–3 phần bảng); mỗi dòng bảng vẫn đúng một phần.
- Tra cứu: con khớp → `Retriever._expand_parents` trả `content` của cha (nhiều con cùng cha → một kết quả); độc lập
  khớp → trả chính nó. Cha chỉ cần `content`, không cần embedding, tóm tắt, câu hỏi.
- Hệ quả: phạm vi Bước 3 và embed của F54 = **246 chunk lá** (không phải 301). Chunk cha: `summary_vi`/`faq_vi`
  trống, `enrichment_status = none`.
- File: contract C2 §8 (bỏ "chunk cha cùng mẫu, tóm tắt cho cả cửa sổ"; "mọi chunk" → "mọi chunk lá"). Không
  đổi code; không sửa dòng D-008 trong `decisions.md` (đã nói cha không được embed để khớp).

## 2026-11-13 · I-43: chỉ chunk lá chịu ngân sách embed; quyết định D-008 (run `f54/eval-h`) · loại: thay đổi

- Vấn đề: đo lại `eval-g` thì 3 chunk vượt ngân sách 650 token (800 − 150 dự trữ Bước 3) đều là **chunk cha**
  (B0036 800 đã `embed_truncated`, B0115 712, B0020 690; `embed_text` của cha gộp mọi con + tới 40 từ khóa); mọi
  chunk lá ≤ 584 token, F86 0 chunk vượt. Mô tả I-43 ban đầu ("chunk không phải bảng") sai.
- Làm rõ (với Toma): 800 là ngưỡng tự đặt ở C2 §8 (model nhận 8.191 token), 650 chỉ để tránh luật cắt của ta;
  kích thước tối ưu cho điểm khớp chưa đo (Bước 4). Tra cứu hiện tại tìm cả cha; cha + con cùng khớp gom một nhóm
  ngữ cảnh nhưng chiếm 2 trong 6 suất top-k (S-03).
- Quyết định (duyệt: Toma; liên luồng → [decisions.md](../../decisions.md) D-008): chỉ tìm trên chunk con/độc lập,
  cha chỉ mở rộng ngữ cảnh. Bỏ phương án tách cửa sổ cha theo token (kế hoạch đầu, bị từ chối).
- Thay đổi: cha không gắn `embed_truncated`; chunk lá vượt ngân sách → cờ `embed_over_budget`; CQ-12 mới (phần
  bảng nhiều dòng vượt → không đạt, lá khác → ghi chú, cha không tính). Không tách cửa sổ, không đổi `content`.
- File: `build/{fields,assertions,quality}.py`; test `test_chunk_quality.py` (+1, mở rộng 1); C2 §5, §8, §10
  (CQ-12), S-03, R-11; [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.16;
  [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md) (I-43); website-qa
  STATE/LOG (việc mở D-008).
- Kiểm chứng: `f54/eval-h` (chép `normalized/` từ `eval-g`, build venv chính, carry từ `eval-g`): 301 chunk, 0
  nội dung đổi, chỉ cha B0036 bỏ cờ `embed_truncated`; 0 lá vượt ngân sách; CQ-01…CQ-12, CQ-RB đạt, độ phủ 1,0,
  ranh giới P/R 1,0; **301 ok / 0 fix / 0 chờ, cổng 2b đạt (tạm)**. Hồi quy `eval-h-regress`: F86 Installation,
  F86 Operation 0 đổi.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 342 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1039 passed, 14 skipped.
- Ảnh hưởng contract/API/schema: C2 như trên; thêm cờ `embed_over_budget`, CQ-12. Phía tra cứu (cột `chunk_role`,
  lọc trong `match_doc_chunks`) chưa làm — cùng bước xuất bản (E-01, BL-22). Không ghi database.
- Mở tiếp: team xác nhận nhãn (`verified: true`); Bước 3 (báo chi phí LLM trước); I-41; I-40 (c), (d).

## 2026-11-12 · Duyệt 7 chunk của `f54/eval-g` — F54 đạt cổng 2b (tạm) · loại: đánh giá

- Duyệt: Toma xác nhận 7 verdict đề xuất; reviewer `toma+claude`.
- `ok` cho 6 chunk mới sau I-40a/I-42: B0069 (cha 2.4.3), B0070 (2.4.3: Figure 50, 51, 52 đúng thứ tự), B0072
  (2.4.4: chỉ Figure 53, 54), B0245 (cha 4.4.3), B0246 (thủ tục 4 điểm + sơ đồ trang 129), B0247 (thủ tục 3 điểm +
  sơ đồ trang 130).
- B0045 `fix` → `ok`: nội dung không đổi, từ khóa OCR rác đã được lọc (I-40b).
- Build lại `eval-g` bằng venv chính (cùng code, chunk không đổi): 301 chunk (cha 55, con 154, độc lập 92),
  **301 ok / 0 fix / 0 chờ**; CQ-01…CQ-11, CQ-RB đạt, độ phủ 1,0, ranh giới P/R 1,0 → **cổng 2b ĐẠT (tạm)**: tạm vì
  nhãn mẫu và nhãn ranh giới còn `verified: false`.
- Tổng kết chuỗi sửa trên F54 (2026-11-11 → 12): `eval-c` 342 chunk, 42 `fix` → `eval-d` (I-37) → `eval-e` (I-38)
  → `eval-f` (I-39) → `eval-g` (I-40a, I-40b, I-42), 0 `fix`.
- Ảnh hưởng contract/API/schema: không. Không đổi code. Không ghi database.
- Mở tiếp: I-43 (P2, nên sửa trước Bước 3); team xác nhận nhãn (`verified: true`); quyết định sang Bước 3 (báo chi
  phí LLM trước); I-41, I-40 (c), (d).

## 2026-11-12 · Sửa I-40a, I-40b, I-42: hình lạc mục, nhãn OCR rác, hai thủ tục dính (run `f54/eval-g`) · loại: thay đổi

- Trước đó: ghi 3 verdict `ok` cho chunk I-39 của `eval-f` (B0115, B0117, B0118; duyệt: Toma qua kế hoạch) →
  `eval-f` 297 ok / 4 fix.
- Vấn đề (4 `fix` còn lại, đều là nội dung thật cần chunk): B0072 mang Figure 52 của mục 2.4.3 (Docling xếp hình đầu
  trang 44 xuống cuối trang); B0045 có từ khóa OCR rác (`DR4-`, `FUL2-`, `PL14+`, `QFF54`…, điểm OCR tới 0,99);
  B0246/B0247 mục 4.4.3 hai thủ tục dính, câu dẫn và sơ đồ lệch thủ tục.
- Quyết định/luật (duyệt: Toma), áp cho mọi tài liệu:
  - T-07 (C1): hình cấp trên nằm hẳn trên heading đánh số đầu trang nhưng xếp sau → dời lên trước, thuộc mục trước,
    cờ `reading_order_fixed`; chỉ trang text layer, cùng cột với heading;
  - R-02 (C2): bước đánh số lại từ 1 → thủ tục mới; câu dẫn ngắn (≤ `procedure_lead_max` 160) và sơ đồ cùng trang
    đi theo thủ tục mới; khối tiêu đề + hình + câu dẫn ngắn ngay trước chuỗi bước gộp vào thủ tục;
  - C2 §8.1: nhãn OCR crop vào từ khóa khi có trong từ vựng text layer của tài liệu hoặc khớp
    `figure_label_trusted_patterns` (qs_controller: PUL/DIR/EDM, X/Y, A/B/Z±, AI/AO, G/M-code, GND/PE/FG, điện áp);
    khác → `figure_labels[].verified = false`. Toma chọn phương án này thay vì chỉ từ vựng (loại 186 nhãn, gồm chân
    đúng `PUL1+`, `DIR1+`, `GND`) hoặc không lọc.
- Lệch kế hoạch: tham số mẫu tin cậy đặt ở cấp profile (`figure_label_trusted_patterns`), không ở `chunking`, vì
  `chunking` của profile con thay nguyên khối của default.
- File: `normalize/sections.py`, `pipeline.py`, `build/{chunker,fields}.py`, `schemas/{profile,chunk}.py`,
  `profiles/{default,qs_controller}.yaml`; test `test_sections.py` (+4), `test_chunker.py` (+2); C1 T-07, cờ; C2
  R-02, §8.1; [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.16;
  [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md) (I-40a/b, I-42 xử lý).
- Kiểm chứng: `f54/eval-g` (chuẩn hóa lại từ raw `eval-f` bằng `.venv-ingest`, build bằng venv chính, carry từ
  `eval-f`): 301 chunk; F54 chỉ 1 hình bị dời (Figure 52 → 2.4.3, sau Figure 51, trước "Note:"); chỉ 2.4.3, 2.4.4,
  4.4.3 đổi nội dung; 4.4.3 → 2 thủ tục (218, 226 token), mỗi thủ tục có câu dẫn, sơ đồ, Step 1–2; nhãn OCR crop
  1.325 giữ / 175 loại; 45 chunk chỉ đổi từ khóa (verdict giữ theo `content_hash`); CQ-01…CQ-11, độ phủ 1,0,
  ranh giới P/R 1,0, BL-34 đạt. Review: 294 ok / 1 fix (B0045, nội dung không đổi) / 6 pending. Hồi quy
  `eval-g-regress`: F86 Installation, F86 Operation 0 chunk đổi, 0 hình dời, 0 từ khóa đổi (không có OCR crop).
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 341 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1038 passed, 14 skipped.
- Ảnh hưởng contract/API/schema: C1 T-07; C2 R-02, §8.1; `FigureLabel.verified` (mặc định `true`, có trong
  `figure_labels` của export `doc_chunks_v1`); profile thêm `procedure_lead_max`, `figure_label_require_vocab`,
  `figure_label_trusted_patterns`. Không ghi database.
- Mở tiếp: duyệt 6 chunk `pending` + đổi B0045 sang `ok`; I-40 (c), (d); I-41; I-43.

## 2026-11-12 · Sửa I-39: chia khối dài theo "Case/Example" (run `f54/eval-f`) · loại: thay đổi

- Vấn đề: khối "How to calculate the electronic gear ratio" (F54 mục 2.6.4.7) vượt 2.500 ký tự nên bị chia
  theo từng phần tử: B0116 (774 token) chứa Case 1, Case 2 và nửa đầu Case 3; kết luận của Case 3 tách sang
  B0117. Bullet là glyph ``.
- Quyết định/luật (duyệt: Toma, theo kế hoạch; C2 R-12 mới), áp cho mọi tài liệu:
  - khối dài có đầu phần (`chunking.block_part_patterns`: Case/Example/Ví dụ/Trường hợp + số) chỉ chia ở đầu
    phần; hình ngay trước đầu phần đi theo phần đó; mỗi phần ≤ 2.500 ký tự và ≤ 650 token `embed_text`;
  - phần 2…n lặp tiêu đề `(phần i/n)` + phần dẫn chung ≤ `block_lead_max` (300 ký tự; ở đây: công thức), vì
    retriever (`_expand_parents`) không kéo chunk láng giềng nên mỗi phần phải tự đủ nghĩa;
  - một phần quá dài → chia theo phần tử trong phần đó, không trộn với phần khác, cờ `block_part_oversize`;
  - glyph vùng Private Use đầu dòng render thành `- ` (`text` của phần tử không đổi).
- Lệch kế hoạch: bỏ ý "`label_heading` giữa khối cũng là đầu phần" vì "Formula:" là `label_heading` và sẽ tách
  công thức khỏi tiêu đề; chỉ dùng mẫu. Thêm: phần của khối bị tách không gộp lại ở bước gộp overview.
- File: `build/{chunker,render}.py`, `schemas/profile.py`, `profiles/default.yaml`; test `test_chunker.py` (+4);
  C2 §6, §6.1, R-11, R-12; [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.16;
  [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md) (I-39 xử lý, I-43 mới).
- Kiểm chứng: `f54/eval-f` (chép raw/normalized từ `eval-e`, build bằng venv chính, carry từ `eval-e`) → 301
  chunk (cha 55, con 154, độc lập 92); chỉ mục 2.6.4.7 đổi: 2 phần (Case 1–2: 551 token; Case 3 + kết luận:
  410 token, lặp công thức); phần 1 cùng ghi chú đầu mục thành cửa sổ cha mới (712 token); CQ-01…CQ-11, độ phủ
  1,0, ranh giới P/R 1,0, BL-34 đạt. Review: 294 ok / 4 fix / 3 pending. Hồi quy `eval-f-regress`: F86
  Installation, F86 Operation 0 chunk đổi.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 335 passed;
  `.\venv\Scripts\python.exe -m pytest tests` → 1032 passed, 14 skipped.
- Ảnh hưởng contract/API/schema: C2 như trên; `Chunking` thêm `block_part_patterns`, `block_lead_max`. Không
  đổi chuẩn hóa, không đổi retriever, không ghi database.
- Mở tiếp: duyệt 3 chunk `pending` của `eval-f`; I-42, I-40, I-41; I-43 (chunk không phải bảng > 650 token).

## 2026-11-12 · Duyệt 9 phần bảng `pending` của `f54/eval-e` (cổng 2b) · loại: đánh giá

- Duyệt: Toma xác nhận đề xuất (qua duyệt kế hoạch); reviewer `toma+claude`.
- B0291–B0299 (bảng 5.1, 5.2, 5.3 sau I-38): cả 9 `ok`. Căn cứ: kiểm tự động mỗi dòng đúng một
  lần, tiêu đề `(phần i/n)` và header lặp ở mọi phần, không phần nào `embed_truncated`; nội dung
  dòng giống các chunk bảng đã đọc ở `eval-d`.
- Build lại `eval-e` bằng venv chính (cùng code, chunk không đổi): 300 chunk, **294 ok / 6 fix /
  0 pending**, 0 stale; CQ, độ phủ 1,0, ranh giới P/R 1,0 đạt. Cổng 2b không đạt chỉ vì 6 `fix`
  (I-39, I-40, I-42); kết quả đánh dấu tạm vì nhãn mẫu `verified: false`.
- Ảnh hưởng contract/API/schema: không. Không đổi code.
- Mở tiếp: I-39 (P1) → lập kế hoạch sửa trước khi đụng code.

## 2026-11-11 · Sửa I-38: chia phần bảng theo token của `embed_text` (run `f54/eval-e`) · loại: thay đổi

- Vấn đề: bảng chia theo ký tự (≤ 2.500) nhưng `embed_text` giới hạn theo token (≤ 800). Bảng
  5.1, 5.2 của F54 có `embed_text` 1.069–1.291 token, chỉ 12–18 dòng đầu vào embedding; phần
  3/3 của 5.1 chỉ có 1 dòng.
- Quyết định/luật (duyệt: Toma, theo bản kế hoạch), áp dụng cho mọi bảng của mọi tài liệu:
  - phần bảng phải thỏa cả ≤ `parent_max` ký tự và `embed_text` ≤ `embed_max_tokens` −
    `embed_enrich_reserve` (tham số mới, 150 token, chừa chỗ cho tóm tắt và câu hỏi của Bước 3);
  - chỉ chia ở ranh giới dòng; chi phí một dòng = token của dòng + token mã của nó trong "Từ
    khóa:"; chi phí được cân giữa các phần;
  - dòng nhóm (một ô có chữ, không mang mã) đi cùng dòng sau nó và được lặp ở phần sau;
  - CQ-11: chunk bảng nhiều dòng có `embed_truncated` làm cổng không đạt.
- File: `build/{chunker,fields,builder,assertions,quality}.py`, `cli.py`, `schemas/profile.py`,
  `profiles/default.yaml`; test `test_chunker.py` (+4), `test_chunk_quality.py`,
  `chunk_helpers.py`; contract C2 §6, §10, §14 (R-05);
  [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.15, §6.16.
- Kiểm chứng: `f54/eval-e` (chuẩn hóa lại từ raw của `eval-d`, build bằng venv chính) → 300
  chunk (cha 54, con 152, độc lập 94); chỉ 3 mục PART 5 đổi; 5.1 → 5 phần 13–15 dòng (545–569
  token), 5.2 → 2 phần (584, 561 token), 5.3 → 2 phần (367, 356 token); mỗi dòng đúng một lần;
  0 `embed_truncated`; CQ-01…CQ-11, CQ-RB đạt, độ phủ 1,0, ranh giới P/R 1,0, BL-34 đạt. Chép
  291/300 verdict (285 ok, 6 fix), 9 `pending` (B0291–B0299, `table_part`).
- Lệch kế hoạch: 5.1 ra 5 phần thay vì ước tính ~6 (sau khi bỏ đếm trùng mã I/O trong chi phí
  dòng); bảng cổng F86 Installation cũng chia lại (đã báo trong kế hoạch). Không gắn cờ mới cho
  khối tiêu đề + hình của I-37 (đã báo ở mục I-37).
- Duyệt 9 phần bảng: đề xuất cả 9 `ok` (kiểm tự động: mỗi dòng đúng một lần, header và tiêu đề
  `(phần i/n)` lặp ở mọi phần, không phần nào bị cắt); **chờ Toma xác nhận**, chưa ghi
  `chunk_review.json`.
- Hồi quy (`eval-d-regress`): F86 Installation 21 → 23 chunk (bảng cổng 2.1: 3 → 6 phần,
  392–529 token), CQ và ranh giới đạt; F86 Operation 0 chunk đổi.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 331
  passed; `.\venv\Scripts\python.exe -m pytest tests` → 1000 passed, 14 skipped.
- Đính chính các mục 2026-11-11 bên dưới: lần build lại `eval-c` và build `eval-d`,
  `eval-c-regress` trong ngày chạy bằng `.venv-ingest` (không có tiktoken) nên `token_count`
  trống và không chunk nào được gắn `embed_truncated`; câu "CQ đạt" ở đó đo bằng ước lượng ký
  tự/4. Đã build lại bằng venv chính: `eval-c` 342 chunk, 300/42/0, 3 chunk `embed_truncated`;
  `eval-d` 296 chunk, 286/10/0, 3 chunk `embed_truncated`. Nội dung chunk, `content_hash` và
  verdict không đổi. Trong lúc sửa, `eval-c` từng bị build nhầm bằng chunker mới (302 chunk), đã
  khôi phục bằng code trước khi sửa I-37 (lấy từ git index).
- Phòng lặp lại: `build` in cảnh báo và đánh dấu kết quả là tạm khi không có tiktoken. Không
  build lại run cũ bằng code mới; kết quả mới luôn vào run id mới.
- Ảnh hưởng contract/API/schema: có, C2 như trên; `Chunking` thêm `embed_enrich_reserve`; cổng 2b
  thêm CQ-11. Không đổi chuẩn hóa. Không ghi database.
- Mở tiếp: duyệt 9 phần bảng `pending` của `eval-e`; I-39, I-40, I-41, I-42. Ước lượng chi phí
  dòng còn dư cho bảng cổng F86 (phần thực tế ≤ 529 token trên ngân sách 650).

## 2026-11-11 · Duyệt tay 66 chunk `pending` của `f54/eval-d` (cổng 2b) · loại: đánh giá

- Vấn đề: sau khi sửa I-37, `f54/eval-d` có 66 chunk đổi nội dung (36 mục) ở trạng thái `pending`.
- Kiểm chứng: đọc từng mục, đối chiếu chunk cũ của `eval-c` với chunk mới (theo `content_hash` +
  `section_path`). Người duyệt `toma+claude` → 64 `ok`, 2 `fix`.
- `fix`: B0245, B0246 (mục 4.4.3, I-42). Cha B0244 ghi `ok` (nội dung cha đủ).
- Ghi chú kèm `ok`: bìa gộp vào lời giới thiệu, mang `ocr_required` (B0000); "Kiểu phát xung
  A/B" gộp vào chunk hình đứng trước (B0114); dòng "Model: F54, F86, Astro 6A, Astro 10i" không
  còn trong `content` (B0260, B0265); bảy mục giới thiệu màn hình có danh sách chức năng loại
  `figure` (I-35); số mục in sai và `section_path` ở gốc (I-40d, I-41).
- Build lại `eval-d`: 296 chunk, CQ đạt, độ phủ 1,0, ranh giới P/R 1,0; duyệt tay 286 ok /
  10 fix / 0 chờ / 0 stale → cổng "Duyệt tay" **không đạt** (10 `fix` mở: I-38 4, I-39 2,
  I-40 2, I-42 2).
- Ảnh hưởng contract/API/schema: không. Không đổi code.
- Mở tiếp: I-38…I-42.

## 2026-11-11 · Sửa I-37: nhãn khung, mục lục lọt, khối tiêu đề + hình (run `f54/eval-d`) · loại: thay đổi

- Vấn đề: 34 trong 42 chunk `fix` của `f54/eval-c` thuộc I-37: chunk hình chỉ có tiêu đề mục
  (21), chỉ có "Model: F54 controller" (8), chỉ có "Instructions / Model: F54" (1), và
  B0000/B0001/B0003/B0004 (bìa, dòng mục lục, "1.1 Overview / Specification:").
- Quyết định/luật (duyệt: Toma, theo bản kế hoạch):
  - T-20 mở rộng: nhãn khung Docling không gom vào picture thành chữ của hình, cờ
    `frame_label_attached`: tiêu đề khung + dòng model liền sau; dòng model ngay trên picture
    hoặc bảng 0 cell. Profile thêm `frame_model_patterns`.
  - T-16 mở rộng: dòng có chấm dẫn ("." hoặc "…") + số trang, và tiêu đề mục lục
    (`toc_title_patterns`) ngay trước mục lục → `toc`, không là heading của T-07.
  - R-04: heading + một dòng dẫn kết thúc ":" (≤ `table_lead_max` 80) trước bảng thành dòng dẫn
    của bảng; khối tiêu đề + hình không caption gộp vào khối sau cùng mục (hết khối thì vào
    khối trước; trước bảng hoặc là nội dung duy nhất của mục thì giữ là chunk hình).
  - R-02: khối thủ tục không nhãn nối với chuỗi khối bước sau; label heading dạng bước được
    đếm là một bước khi phân loại (một phần I-35, duyệt bổ sung trong lúc làm).
- File: `normalize/{figures,coverage,sections,elements}.py`, `pipeline.py`, `build/chunker.py`,
  `schemas/profile.py`, `profiles/default.yaml`; test `test_text_frames.py`, `test_coverage.py`,
  `test_chunker.py` (+9); contract C1 (T-16, T-20, cờ), C2 §14 (R-02, R-04);
  [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.7, §6.15, §6.16.
- Kiểm chứng: `f54/eval-d` chuẩn hóa lại từ raw của `eval-c` → 296 chunk (cha 54, con 152, độc
  lập 90); 36 mục đổi; 34/34 chunk `fix` của I-37 không còn; CQ-01…CQ-10, CQ-RB đạt, độ phủ
  1,0, ranh giới P/R 1,0, BL-34 đạt. Chép 230/296 verdict (222 ok, 8 fix), 66 `pending`.
- Hồi quy (run `eval-c-regress`, không render ảnh): F86 Installation 26 → 21 chunk (bìa sạch,
  chunk mục lục `toc_like` biến mất, mục 2.5 và 2.6 gộp sơ đồ với NOTE), CQ, độ phủ, ranh giới,
  BL-34 đạt; F86 Operation 0 chunk đổi; F10T chỉ "CONTENT" → `toc`.
- Test, từ `backend/`: `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 327
  passed; `.\venv\Scripts\python.exe -m pytest tests` → 996 passed, 14 skipped.
- Lệch kế hoạch: không gắn cờ `assets_attached_to_neighbor` cho khối tiêu đề + hình (tiêu đề đã
  nằm trong `content`). F86 Installation có đổi (kế hoạch kỳ vọng 0), đã liệt kê ở trên.
- Ảnh hưởng contract/API/schema: có, C1 và C2 như trên; `Profile` thêm 2 trường, `Chunking`
  thêm 1 trường. Luồng tra cứu không đổi. Không ghi database.
- Mở tiếp: I-42 (mục 4.4.3 hai thủ tục dính nhau, phát sinh từ thay đổi này; giữ nguyên theo
  quyết định duyệt); duyệt 66 chunk `pending` của `eval-d`; I-38…I-41.

## 2026-11-11 · Duyệt tay 36 chunk `pending` của `f54/eval-c` (cổng 2b) · loại: đánh giá

- Vấn đề: sau T-20, `f54/eval-c` còn 36 chunk `pending` (13 mục đổi nội dung so với `eval-b`).
- Kiểm chứng: đọc nội dung từng chunk, đối chiếu với ghi chú của `eval-b` (danh sách Step và
  phần tử bị loại do I-36). Mọi Step bị mất trước đây đã có mặt, câu bị cắt đã đủ (vd. 3.4
  Step 3; 4.3.3 Step 1–4; 3.3.4 Step 1–5; 4.10.1 và 4.11.2 Step 1–8). Không mở lại PDF gốc.
- Kết quả (người duyệt `toma+claude`): 30 `ok`, 6 `fix`. `fix`: B0247, B0250, B0254, B0285,
  B0317, B0321, đều là chunk hình chỉ có tiêu đề mục (I-37). Ghi chú kèm `ok`: nhãn khung
  "Instructions / Model: F54" còn sót, có chỗ chen giữa thủ tục (B0316, B0327; I-37, không
  chặn); thủ tục ngắn chia ở Step 3 (B0308/B0309, B0328/B0329); B0286 sai `chunk_type` (I-35).
- Build lại `eval-c` với `--labels tests\doc_ingest\fixtures\eval\f54.chunks.json`: 342 chunk,
  CQ đạt, độ phủ 1,0, ranh giới P/R 1,0; duyệt tay 300 ok / 42 fix / 0 chờ / 0 stale → cổng
  "Duyệt tay" **không đạt** (42 `fix` mở).
- Phát hiện mới: I-41 (P2). Số mục in sai 3.3.x làm lệch `section_path`: 3.3.4, 3.3.5, 3.9.2 và
  cả `4.3.6 Copy and Paste` (số đúng) thành mục gốc, mất `PART 4 > 4.3`. Thêm vào
  [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md).
- Ghi chú: verdict chép từ `eval-b` giữ nguyên ghi chú cũ; vài mục `fix` (vd. B0229) còn ghi lý
  do I-28 dù nay là chunk hình chỉ có tiêu đề (I-37). Verdict vẫn đúng, không sửa ghi chú.
- Ảnh hưởng contract/API/schema: không. Không đổi code.
- Mở tiếp: sửa I-37 (nhóm `fix` lớn nhất), rồi I-38…I-41.

## 2026-11-11 · Tách nhật ký chunking sang cấu trúc theo luồng (D-002) · loại: thay đổi

- Vấn đề: `chunking_flow_log.md` gộp trạng thái, lịch sử, quyết định và backlog nên tự
  mâu thuẫn: tiêu đề ghi cập nhật 11-09 trong khi mục 1 có nội dung 11-10, 11-11; mục 7 ghi
  "0 ok / 323 chờ" còn mục 1 ghi "270 ok / 53 fix"; I-36 và T-20 thiếu ở mục 5, 6; mục 4
  không có mục ngày 11-10, 11-11.
- Quyết định/luật: tách thành `README.md` (mục 2, 3 cũ + phần thiết kế từ
  `architecture.md`), `STATE.md` (mục 1, 8 cũ), `LOG.md`; mục 4–8 cũ chép nguyên văn vào
  `LOG-archive-2026-11-09.md` (duyệt: Toma, D-002 trong [decisions.md](../../decisions.md)).
- File: `docs/ai/flows/doc-ingest/*`; `docs/ai/chunking_builder/chunking_flow_log.md` còn
  là con trỏ; `architecture.md` và `current-state.md` rút phần `doc_ingest` còn tóm tắt.
- Kiểm chứng: số trong STATE đọc lại từ `data/ingest_runs/*/build/chunk_review.json` và
  `chunk_quality.json` → khớp các mục 11-10, 11-11 bên dưới. Từ `backend/`:
  `..\.venv-ingest\Scripts\python.exe -m pytest tests\doc_ingest` → 318 passed.
- Ảnh hưởng contract/API/schema: không. Không đổi code.

## 2026-11-11 · T-20 khung chữ và `build --carry-review` (sửa I-36 trên trang text layer) · loại: thay đổi

- Vấn đề: I-36 (P0). Trên trang text layer của F54, Docling nhận khung cột "Instructions"
  là picture, nên 39 đoạn hướng dẫn trên 23 trang thành `figure_text` và các chunk thủ
  tục thiếu Step.
- Quyết định/luật: luật chuẩn hóa mới T-20 "khung chữ", chạy trước T-17. Picture thực chất
  là khung hướng dẫn (nhãn Step hoặc câu văn, phần lớn dòng nhiều từ, không phải tiêu đề
  khung) trả chữ về text thân theo thứ tự đọc, cờ `frame_text_released`; picture gắn cờ
  `text_frame`; tiêu đề khung ("Instructions", "Model: F54") giữ là `figure_text`. Chỉ áp
  dụng cho trang text layer; trang OCR không đổi (I-28 còn mở).
- Quyết định/luật: `build --carry-review <chunk_review.json> --carry-chunks <chunks.jsonl>`
  chép verdict của lần build trước theo `content_hash` + `section_path`; chunk mới, đổi nội
  dung hoặc đổi mục thành `pending`.
- File: `normalize/figures.py`, `build/builder.py`, `cli.py`; test
  `tests/doc_ingest/test_text_frames.py`; contract C1 (thứ tự T-20 → T-17, cờ mới) và C2
  (lệnh `--carry-review`); [p1_golden_tests.md](../../reports/p1_golden_tests.md) §6.16.
- Kiểm chứng: run mới `f54/eval-c`, chuẩn hóa lại từ raw của `eval-b`, không ghi đè
  `eval-b` → 342 chunk (cha 70, con 197, độc lập 75); đúng 13 mục đổi so với `eval-b`, mọi
  mục có đủ Step; CQ-01…CQ-10 và CQ-RB đạt, độ phủ 1,0, ranh giới P/R 1,0; BL-34 đạt;
  `figure_text` bị loại trừ 518 → 449. Chép 306/342 verdict (270 ok, 36 fix), 36 `pending`.
  F86 Installation, F86 Operation, F10T: 0 khung.
- Ảnh hưởng contract/API/schema: có, C1 (luật T-20, cờ `text_frame`, `frame_text_released`)
  và C2 (tùy chọn CLI). Luồng tra cứu không đổi.
- Mở tiếp: duyệt 36 chunk `pending` của `eval-c`; I-37 (chunk hình chỉ có tiêu đề mục, nhãn
  khung còn lại ở trang Docling không gom khung), I-38, I-39, I-40.

## 2026-11-10 · Duyệt tay cổng 2b trên F54 (run `f54/eval-b`) · loại: đánh giá

- Vấn đề: cổng 2b cần verdict của người duyệt cho từng chunk; trước đó toàn bộ `pending`.
- Kiểm chứng: `chunk_review.json` của `f54/eval-b`, người duyệt `toma+claude` → 270 ok /
  53 fix / 0 chờ trên 323 chunk. Build lại `eval-b`: cổng "Duyệt tay" **không đạt** (53 fix
  mở), 0 stale.
- Nhóm `fix`, theo nhật ký cũ:
  - mất Step do khung "Instructions" bị nhận là picture: I-36 (P0), 18 chunk;
  - chunk gần rỗng và ảnh tách khỏi hướng dẫn: I-37, 27 chunk;
  - bảng tham số vượt 800 token: I-38, 4 chunk;
  - `block_split` cắt giữa ví dụ: I-39, 2 chunk;
  - Figure 52 sai mục và từ khóa OCR rác: I-40, 2 chunk.
- Ghi chú trong `chunk_review.json` được viết trước khi có ID I-36…I-40 và dùng nhãn I-28
  (18 chunk), I-33 (13 chunk); không sửa lại file đó.
- Lỗi của PDF gốc (số mục 3.9.x, chữ tiếng Việt, `M1951`/`M1950`) ghi `ok` kèm ghi chú.
- Ảnh hưởng contract/API/schema: không.
- Mở tiếp: I-36…I-40 (thêm vào
  [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md));
  F86 Installation chưa duyệt.
