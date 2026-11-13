# Sổ quyết định liên luồng

Cập nhật: 2026-11-13

Chỉ ghi quyết định ảnh hưởng từ hai luồng trở lên hoặc tới quy tắc chung. Quyết định của
một luồng ghi thành mục loại "quyết định" trong `LOG.md` của luồng đó. Không sửa dòng cũ:
quyết định bị thay thế thì đổi cột Trạng thái và thêm dòng mới.

| ID | Ngày | Phạm vi | Quyết định | Lý do | Duyệt | Trạng thái |
|---|---|---|---|---|---|---|
| D-001 | không ghi ngày (trước 2026-11) | chat (website, CRM) | Lịch sử chat lưu bằng model `ChatHistory` vào bảng Supabase `public.chat_history`. Truy cập DB chỉ qua `HistoryRepository` và `ChatbotService`; route chỉ làm dependency wiring và SSE. Request không có `session_id` nhận UUID do backend sinh. Stream xong ghi `status='completed'`, lỗi provider ghi `status='error'`. | Giữ tách lớp transport và persistence. | không ghi | hiệu lực, xem ghi chú |
| D-002 | 2026-11-11 | tài liệu cho agent | Tài liệu tách theo luồng: `AGENTS.md` là chỉ mục chung; mỗi luồng có `README.md`, `STATE.md`, `LOG.md` trong `docs/ai/flows/`; quy tắc chung ở `docs/ai/rules/`. Làm từng đợt, thí điểm với `doc-ingest`. | Agent phải đọc khoảng 2.200 dòng cho task một luồng; nhật ký chunking gộp trạng thái và lịch sử nên tự mâu thuẫn. | Toma | hiệu lực |
| D-003 | 2026-11-11 | tài liệu cho agent | Tài liệu cho agent viết bằng tiếng Việt; tên file, ID, mã lỗi, lệnh giữ tiếng Anh. | Khớp với phần lớn tài liệu hiện có; team duyệt nhanh hơn. | Toma | hiệu lực |
| D-004 | 2026-11-11 | deploy | Hạ tầng deploy chưa chốt. Trước mắt chỉ có checklist không phụ thuộc hạ tầng ở [rules/deploy-rules.md](rules/deploy-rules.md). | Repo chưa có cấu hình deploy thực tế để trích quy tắc. | Toma | hiệu lực |
| D-005 | 2026-11-10 | crm-agent, chính sách dữ liệu | Số liệu CRM: phương án C thay phương án A. LLM tự dựng query trên mọi bảng Reporting API qua `crm_schema` + `crm_query`; mặc định `CRM_TOOLS=query`; A (`crm_report` + `crm_records`) còn chạy qua `CRM_TOOLS=catalog`. Mở mọi dữ liệu nghiệp vụ kể cả liên hệ khách hàng và chat; chặn khóa và bí mật (`reporting/raw/policy.py`). | Catalog cố định không theo kịp câu hỏi thực tế (vụ "Hohmeier"). Hệ quả: dữ liệu CRM đi tới nhà cung cấp LLM và có thể nằm trong `chat_history`. | Toma | hiệu lực; thay quyết định "phương án A" cùng ngày |
| D-006 | 2026-11-11 | crm-agent, quy tắc chung | Ngoại lệ của TR-16/DR-03: `CRM_CHAT_FLOW` mặc định `agent` dù luồng agent đang thử nghiệm. Tool CRM vẫn sau `CRM_REPORT_ENABLED` (mặc định tắt). | Toma đang kiểm thử luồng báo cáo CRM trên kênh CRM; rollback bằng `CRM_CHAT_FLOW=pipeline` (DR-11). Xem lại khi hết giai đoạn kiểm thử hoặc trước deploy production. | Toma | hiệu lực, tạm thời |
| D-007 | 2026-11-11 | tài liệu cho agent | `backend/scripts/check_ai_docs.py` kiểm cấu trúc tài liệu (liên kết, giới hạn dòng, đủ 3 file mỗi luồng, dòng `Cập nhật:`, thứ tự LOG, `paths:` của rule); `backend/tests/test_check_ai_docs.py` chạy nó trên repo thật nên tài liệu lệch làm pytest backend fail. | Giữ tài liệu không lệch dần sau D-002; CI hiện chưa chạy test backend. | Toma (duyệt kế hoạch Đợt 4) | hiệu lực |
| D-008 | 2026-11-13 | doc-ingest, website-qa, chat-platform (SQL `doc_chunks`) | Tra cứu tài liệu (vector + FTS) chỉ tìm trên chunk **con và độc lập**; chunk cha (cửa sổ ngữ cảnh) không được embed để khớp, chỉ dùng để mở rộng ngữ cảnh khi một con của nó khớp. Ngân sách `embed_text` (800 − 150 token dự trữ Bước 3) chỉ áp cho chunk lá; cửa sổ cha giới hạn theo ký tự (2.500). | Khi tìm cả cha, cha và con cùng khớp chiếm 2 trong 6 suất top-k (S-03 của contract C2) dù LLM chỉ nhận nội dung cha một lần; `embed_text` của cha gộp mọi con + từ khóa nên vượt ngân sách (F54: 3 cha 690–800 token, I-43). Ngưỡng 800 là ngưỡng tự đặt ở C2 §8, không phải giới hạn model. | Toma | hiệu lực phía doc-ingest; phía tra cứu chưa làm (cần cột `chunk_role` + điều kiện trong `match_doc_chunks`, cùng bước xuất bản/Bước 5); đo lại ở Bước 4 |
| D-009 | 2026-11-13 | doc-ingest, website-qa, chat-platform (SQL) | Bảng tra cứu tài liệu mới **`doc_chunks_v2`** + hàm `match_doc_chunks_v2`, tạo song song bảng `doc_chunks` cũ (3 dòng thử). Duyệt mọi điểm "C" của [p2_doc_chunks_schema_review.md](reports/p2_doc_chunks_schema_review.md): `doc_version`, `chunk_key`, `chunk_role` (D-008), `printed_page_*`, `codes`, `embedding_model`, `source`, `review_status`, `source_run`; bỏ check danh sách model cứng (loader kiểm theo registry); loader embed trước rồi insert trong một transaction, gán `parent_id` thật (E-01); sửa lọc model rỗng (E-05). **Retriever chỉ dùng chunk `review_status = approved`**; giai đoạn đo được tắt điều kiện này qua tham số. `approved` = cổng 2b đạt **không tạm** (nhãn đã xác nhận) + verdict `ok` + (chunk lá) làm giàu đã duyệt 2c. Cài `unaccent` trong SQL v2 để đo bỏ dấu; không có lợi thì không áp dụng. | Bảng/hàm cũ là bản thiết kế thử, lệch với DB thật (§1 tài liệu); cần chốt trước đợt nạp chunk từ luồng chunking cho mọi PDF. | Toma | hiệu lực; các điểm "Đ" (nhánh mã, bỏ dấu, cộng điểm loại, áp dụng model cấp chunk) quyết sau khi đo |

## Ghi chú

- D-001, phần đã thay đổi so với bản ghi gốc (đối chiếu code 2026-11-11):
  - `session_id` của kênh website do `widget-backend` giữ trong cookie HttpOnly
    `qs_chat_session` (đọc từ header `X-Session-ID`), không còn do frontend lưu.
  - Endpoint đọc lịch sử `GET /chatbot/sessions/{id}/history` đã có, nhưng chưa có xác
    thực hay kiểm tra ownership (`chatbot/routers/workspace.py`); xem DR-05 trong
    [rules/deploy-rules.md](rules/deploy-rules.md).
