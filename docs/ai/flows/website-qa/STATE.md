# Trạng thái luồng website-qa

Cập nhật: 2026-11-14

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- Chạy trọn luồng: security → context → làm rõ → analysis → retrieve → stream câu trả lời.
- Retrieval mới kiểm **ở mức test**: chưa kiểm với Supabase thật, tham số chưa tối ưu, chưa
  rerank.
- Handoff là scaffold: không tạo ticket, `mode` luôn là `bot`.
- Chưa gửi nguồn hoặc ảnh về frontend qua SSE; số `[S#]` đánh lại từ S1 mỗi lượt.
- Chưa có eval cho luồng.

## Độ chín từng phần

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| SecurityStage | có | [security-stage-pipeline.md](../../security-stage-pipeline.md) |
| Context, Prune, `ConversationState` | có | Cần cột `chat_history.conversation_state` (thêm tay, chưa kiểm live); chưa nạp summary |
| Vòng làm rõ | có | |
| Analysis đa ngôn ngữ | có | Câu cố định chỉ có `vi`, `en` |
| Retrieve hybrid có lọc | có, mức test | Không rerank, không `unaccent` cho FTS; chưa dùng `chunk_type`, `doc_type`, `keywords` |
| Handoff | scaffold | Chưa nối nền tảng nhân viên, chưa có đường trả về `mode=bot` |
| SSE nguồn/ảnh | chưa có | |
| `chat_history.retrieved_chunk_ids` | chưa điền | Cột là `UUID[]`, `doc_chunks.id` là `bigint` |

## Vấn đề mở

| ID | Vấn đề |
|---|---|
| H1 | Handoff hứa chuyển nhân viên nhưng không tạo ticket |
| H6 | `[S#]` không lưu, đánh lại mỗi lượt |
| E-05 | Nhánh FTS của `match_doc_chunks` bỏ mọi dòng khi bộ lọc model là mảng rỗng (nhánh vector coi là không lọc); ghi ở [p2_chunk_contract.md](../../reports/p2_chunk_contract.md). **Trên Supabase thật nặng hơn** (đọc 2026-11-13): cả hai nhánh dùng `p_models is null` → `[]` làm cả vector lẫn FTS trả rỗng |
| L-2 | Supabase thật chưa áp `migrate_product_models_crm.sql`: check `product_models` còn ASTRO_*; `embedding` nullable (repo ghi not null). Chi tiết: [p2_doc_chunks_schema_review.md](../../reports/p2_doc_chunks_schema_review.md) §1 |
| L-4 | Supabase thật có 0 dòng `technical_docs` (3 dòng thử: product_catalog, company_info) trong khi registry khai báo coverage F86 |
| R-1 | Bước phân tích chọn sai intent → sai domain: 40 câu đúng cả ba 0,875 (D21 "#12100", D30 không dấu → `lookup.product_info`; D06 → troubleshoot). Kế hoạch: rà soát độ phủ intent/trường ↔ chunk trước, rồi luật code có phiên bản, fallback khi yếu, mô tả intent |
| R-2 | **Đã chốt cộng điểm 0,003** (Toma 2026-11-14). 40 câu web2: lọc 0,735 / 0,673 → 0,853 / 0,798; 8 câu scope MRR 1,0. Chưa đổi mặc định `MatchV2Options` (làm cùng R-1) |
| R-3 | `coverage` của registry viết cứng (chỉ F86); nạp tài liệu mới phải sửa code |
| R-4 | FTS OR từ phổ biến làm chunk tổng quan thắng chunk đúng. `fts_clean` **đã bật** mặc định ở repository v2 (Toma 2026-11-13; core MRR 0,643 → 0,861); vẫn đo song song (`no_fts_clean`) với câu hỏi đa dạng |
| D-008 | Quyết định 2026-11-13: chỉ tìm trên chunk con/độc lập, cha chỉ mở rộng ngữ cảnh ([decisions.md](../../decisions.md)). Chưa làm: cột `chunk_role` trong `doc_chunks` + điều kiện trong `match_doc_chunks`; làm cùng bước xuất bản chunk builder (loader mới, E-01) |
| — | Mã model dính chữ tiếng Việt ("F86có") không còn được nhận vì yêu cầu ranh giới mã |
| — | Dữ liệu capabilities của F86E, 6AHE, 6AVE, 10iV, 10iVE là tạm (chép từ model gốc); Supabase cần `backend/sql/migrate_product_models_crm.sql` |

## Kết quả kiểm gần nhất

2026-11-11:
- Từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests` → 938 passed, 14 skipped.
- Trong `widget-backend/`: `npm test` → 22 pass.
- Từ root: `npm run build` đạt; `npm run lint` lỗi sẵn có (429 lỗi: 139 trong `src/`, 290 do
  eslint quét `.claude/worktrees/`).

## Bước tiếp theo

1. `doc_chunks_v2` + `match_doc_chunks_v2` đã áp lên Supabase (2026-11-13, D-009,
   [p2_doc_chunks_schema_review.md](../../reports/p2_doc_chunks_schema_review.md)); đã nạp F54 (296) + F86
   Installation (23), đều `draft`. Eval 14 câu: core recall@5 0,929; web lượt 2 recall@5 0,643; định tuyến đúng cả
   ba 0,786 (R-1…R-4). Tiếp: tối ưu định tuyến + trộn điểm dần dần (kế hoạch riêng), bộ câu hỏi lớn dần.
2. Sửa E-05 (trong `match_doc_chunks_v2`).
3. SSE nguồn/ảnh và quyết định kiểu `retrieved_chunk_ids`.
4. Handoff thật (H1), lưu `[S#]` qua lượt (H6).
5. Eval cho luồng website.
