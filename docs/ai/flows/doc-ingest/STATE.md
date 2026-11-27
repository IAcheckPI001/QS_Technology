# Trạng thái luồng doc-ingest

Cập nhật: 2026-11-26 (đối chiếu git và Supabase thật, chỉ đọc)

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- Hai đường tạo chunk nháp: PDF → S0/Docling → chuẩn hoá T-xx/V-01 → `build`; dữ liệu catalog biên soạn → `curated-build` (`source=manual`). Builder không ghi DB; `chunking_loader` nạp run vào `doc_chunks_v2` (draft). Chat đọc `doc_chunks_v2` từ 2026-11-19.
- **Git:** T-15b (`a0ce51a`), lớp vá ô T-21 (`c3b1177`, 13 vá `verified`), T-20b (`aba3a6d`) đã có trên `origin/feature/deploy_ai_service`. **Staged, chưa commit:** S0 trang lai + T-22 (vá tiêu đề OCR hỏng, 3 vá `proposed`), bỏ asset ảnh lồng trong ô bảng, catalog phương án C (35 lát theo model) và `--no-slices`.
- **DB (Supabase thật, 2026-11-26):** `doc_chunks_v2` 1.057 dòng, 983 active, **0 approved**. 911 chunk CRM `draft` của 10 tài liệu (Installation F54/F86 `crm-1.4-a`, 6AVE/F10T `crm-1.2-a`; Operation F10T `crm-1.2-a`, F86/F54/6AVE `crm-1.6-a`, 6AH/10iV `crm-1.6-b`) + 72 chunk catalog `curated-b2` (active); 37 + 37 catalog inactive (A `curated-a`, B `curated-b3`, dùng đo). 808/983 dòng active có `review_blockers`. Ảnh của run mới chưa `publish-assets`. Sao lưu (ngoài repo): `E:\backups\QS_Technology\doc_chunks_v2_all_2026-11-25.jsonl`.
- **Verdict (model duyệt, chưa người xác nhận):** run đã nạp 911 chunk = 596 `ok`, 307 `fix`, 8 `pending`; run `crm-1.7-a` (S0 trang lai + T-22, chưa nạp) 925 = 623 / 291 / 8.
- **Chunk "đạt" ≠ tra cứu tốt (I-61, [báo cáo](../../reports/chunk_pass_vs_retrieval_2026-11-26.md)):** tiêu chí đạt (CQ, mã chặn, verdict, cổng 2b/2c) chỉ đo độ trung thực; 130/786 chunk lá CRM dưới 80 ký tự (phần lớn tiêu đề hình `ok` theo `[image_only_info]`); tài liệu kỹ thuật đo web1 recall@5 0,42 so với catalog ≈ 1,0.

## Tiêu chí chunk đạt (theo code)

| Tầng | Điều kiện |
|---|---|
| Cấu trúc | CQ-01…CQ-12 đạt, độ phủ phần tử 1,0 và 0 lặp (`build/assertions.py`, `quality.py::gate`) |
| Không mã chặn | `review_blockers` rỗng (`ocr_required`, `heading_garbled`, `text_patch_unmatched`…) |
| Nội dung | verdict `ok` đúng `content_hash` (chữ khớp PDF; sơ đồ chỉ trong ảnh: `ok` + `[image_only_info]`) |
| `approved` | ba tầng trên + cổng 2b không tạm (ranh giới P/R ≥ 0,9 trên nhãn đã xác nhận, 0 `fix` mở) + làm giàu 2c duyệt (lá); `manual`: `curated_verified` (`export/doc_chunks_v2.py::review_status`) |
| Tìm được | **chưa có** (I-61) |

## Độ chín từng bước

| Bước | Luật | Trạng thái | Backlog |
|---|---|---|---|
| Nguồn CRM (plan, fetch, status) | — | có (giai đoạn 1); chưa chạy theo lịch | — |
| S0 + OCR theo trang, parse Docling | — | có; trang lai ép OCR (staged); OCR chỉ tiếng Anh (I-29) | BL-24 |
| Khung chữ, header/footer, nhãn, mục lục | T-20, T-20b, T-17, T-18, T-16 | có; T-20b trên trang OCR đã merge | BL-07, BL-10, BL-33 |
| Bảng; vá ô, vá dòng chữ | T-01…T-05, T-15, T-15b; T-21; T-22 | có; T-22 staged; 23 hàng mồ côi Operation; F10T/6AVE Installation chưa vá | BL-05, BL-06, BL-11, BL-27 |
| Trang in, section path, list | T-06, T-07, T-08 | có | BL-07…BL-09 |
| Hình | T-09…T-11, T-14, T-19 | có; ảnh màn hình thành bảng (I-57), chunk hình gộp trang (I-60) | BL-10 |
| Kiểm bất biến | V-01…V-04 | một phần: chỉ V-01 | BL-25 |
| Chunk builder + kiểm 2b | C2 | có; 2b chỉ đo trên F54/F86 Installation (nhãn chưa xác nhận) | BL-15, BL-16 |
| Làm giàu (2c) | C2 §8 | có trong code; v5 F86 không đạt (chunk chỉ tiêu đề hình) | — |
| Catalog biên soạn | C2 §15 | có; C active trên DB, kết quả đo lẫn lộn | — |
| Xuất bản → `doc_chunks_v2` | — | draft nạp được; chưa có `approved`, chưa theo sổ nguồn | BL-22 |

## Vấn đề mở

| ID | Mức | Vấn đề |
|---|---|---|
| I-61 | P0 | Không có cổng "tìm được": chunk/tài liệu có thể `approved` mà câu hỏi thật không tìm ra hoặc ngữ cảnh không đủ trả lời; chưa có câu vàng theo tài liệu |
| I-53 | P0 | Không có cơ chế gỡ mã chặn: 808 dòng active có `review_blockers` → luôn `draft`; `approved` còn cần 2b không tạm và 2c |
| I-55 | P0 | 10iV tr.107–110 mất chữ số (`#0000` → `# `); kiểm S0 đã có, chờ parse lại 10iV bằng OCR ép |
| I-56 | P0 | Bảng cổng Installation gán sai chân: F54/F86 đã vá (T-21); F10T (X57, CN4/CN5, CN8), 6AVE (CN7+8+9 gộp) chưa |
| I-51, I-29 | P0 | Bản Operation là ảnh scan; F10T OCR tiếng Anh trên tài liệu Việt (rớt dấu, ≥ 49/147 chunk) |
| I-58 | P1 | Sơ đồ chỉ còn caption: chính sách `ok` + `[image_only_info]`, nhưng chunk không đủ để trả lời (xem I-61) |
| I-57, I-59, I-60 | P1 | Ảnh màn hình thành bảng; ảnh nuốt chữ (T-20b sửa phần lớn); chunk hình gộp nhiều trang |
| I-54 | P1 | V-01 báo động giả, bỏ sót lỗi thật |
| I-47…I-50, I-52 | P0–P1 | Brochure → nguồn `curated/`; bản F54 Operation trên CRM khác V.02 |

Mô tả đầy đủ: [p1_chunking_impact_assessment.md](../../reports/p1_chunking_impact_assessment.md); I-55…I-60: [báo cáo kiểm duyệt](../../reports/p4_crm_chunk_review_2026-11-20.md); kết quả duyệt chunk run `crm-1.0-a` (847 mục, 2026-11-21, người duyệt tự động, chưa người xác nhận): [p4_crm_chunk_review_2026-11-21](../../reports/p4_crm_chunk_review_2026-11-21.md); kế hoạch fix/pending: [p4_fix_pending_plan](../../reports/p4_fix_pending_plan_2026-11-25.md).

## Tài liệu tham chiếu

| Báo cáo | Dùng để | Số liệu có thể đã cũ |
|---|---|---|
| [doc_chunks_v2_column_roles_2026-11-25](../../reports/doc_chunks_v2_column_roles_2026-11-25.md) | Vai trò, mức quan trọng của 43 cột `doc_chunks_v2`; căn cứ bước duyệt chunk | Số dòng và phân bố trong DB (948 dòng, 911 + 37; `standalone`/`child`/`parent`) là ảnh chụp 2026-11-25, đã lệch sau khi nạp catalog C. Báo cáo này cũng tự ghi STATE cũ (1.203 chunk) lệch DB. Đếm lại bằng Supabase trước khi trích |
| [p4_crm_chunk_review_2026-11-21](../../reports/p4_crm_chunk_review_2026-11-21.md) | Kết quả duyệt `crm-1.0-a` theo tài liệu | Số `ok`/`fix`/`pending` ứng với run `crm-1.0-a`; run đã nạp và `crm-1.7-a` có số khác (xem Tóm tắt) |
| [chunk_pass_vs_retrieval_2026-11-26](../../reports/chunk_pass_vs_retrieval_2026-11-26.md) | Bằng chứng I-61 | Recall@5 và số chunk dưới 80 ký tự đo ngày 2026-11-26, đổi khi nạp lại hoặc đổi catalog |

Quy ước: số trong báo cáo ghi theo ngày đo; muốn dùng số hiện tại thì đọc mục Tóm tắt và Kết quả kiểm gần nhất ở trên, hoặc đo lại.

## Kết quả kiểm gần nhất

- 2026-11-26, Supabase thật (chỉ đọc): số ở Tóm tắt; `chat_traces` từ lúc nạp lại 14 lượt website (9 có tra cứu, chỉ trúng catalog, F54 Installation/Operation), CRM 0 lượt; trace không ghi id chunk.
- Test (2026-11-25, sau sửa asset lồng và catalog): `pytest tests\doc_ingest` 454 passed (venv ingest).
- Catalog (20 câu, core r@1 / web2 r@1): A 0,60 / 0,65; B 0,35 / 0,70; C0 0,25 / 0,25; C1 0,60 / 0,80 (LOG 2026-11-25).

## Bước tiếp theo

1. **Toma:** duyệt merge S0 trang lai + T-22 và 3 vá tiêu đề; quyết giữ catalog C hay lui A; quyết tầng "tìm được" (I-61: số câu vàng mỗi tài liệu, ngưỡng); chính sách chunk chỉ-tiêu-đề (gộp cha / không embed / bỏ FAQ).
2. Agent: commit phần staged khi được duyệt; nạp `crm-1.7-a`; `publish-assets --apply` cho run đã nạp.
3. Vá F10T/6AVE Installation (T-21, cần tách hàng cho 6AVE); parse lại 10iV (I-55); OCR tiếng Việt F10T (I-29).
4. Bộ vàng theo tài liệu (website-qa GD1) làm cổng trước khi mở `approved`; sau đó I-53 (gỡ `ocr_required`), cổng 2b/2c.
5. Giai đoạn 2 crm-sync: nạp theo sổ nguồn, gỡ bản cũ, `crm-plan` theo lịch; V-02…V-04, trích fact.
