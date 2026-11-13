# Trạng thái chat-platform

Cập nhật: 2026-11-11

Ảnh chụp trạng thái hiện tại. Viết lại khi có thay đổi; lịch sử ở [LOG.md](LOG.md).

## Tóm tắt

- Service key theo kênh, session theo principal, lease theo phiên, ghi history 4 trạng thái
  (`completed`, `error`, `blocked`, `cancelled`) và trace trong tiến trình đều có code và test.
- **Chưa kiểm với Supabase thật**: chưa có lần `/health/db`, insert/select `chat_history` hay
  lease trên khóa dòng thật nào được ghi lại.
- Các GET `/chatbot/...` của Support Workspace **chưa có xác thực hay ownership**.
- `Idempotency-Key` mới được lưu, chưa chống xử lý trùng.

## Độ chín từng phần

| Phần | Trạng thái | Ghi chú |
|---|---|---|
| Service key theo kênh | có | Chưa có scope theo integration, rate limit theo key, `last_used_at` |
| Session + ownership khi ghi | có | Xóa hội thoại chưa có |
| Turn lease | có, test bằng fake | Khóa dòng thật cần kiểm live |
| Ghi `chat_history` | có | Token và chi phí là ước tính từ text câu hỏi/trả lời |
| Đọc history, retrieval, trace, conversations | có, không xác thực | Giữ nội bộ |
| Tracing giai đoạn 0 | có | Chưa OpenTelemetry, chưa truyền `traceparent` sang CRM/OpenAI, chưa retention, chưa UI |
| Health | một phần | `/health/db` chỉ `SELECT 1`; chưa định nghĩa readiness, chưa kiểm schema |

## Vấn đề mở

| Mức | Vấn đề |
|---|---|
| Cao | `requirements.txt` cho phép `fastapi>=0.115`; FastAPI 0.106–0.117 đóng dependency trước khi stream xong nên history ghi trong stream không commit. Chưa quyết định nâng mức tối thiểu |
| Cao | Key CRM là tin cậy ủy quyền: `user_id` do CRM backend khẳng định; key lộ thì mạo danh được mọi nhân viên của integration (chỉ có thu hồi + cấp lại) |
| Trung bình | GET `/chatbot/...` không ownership; `/chatbot/conversations` liệt kê mọi session |
| Trung bình | Retry sau khi lượt gốc xong vẫn chạy lại (không replay theo `Idempotency-Key`) |
| Thấp | Usage thật của provider có trong trace nhưng chưa ghi về `chat_history`, chưa đổi ra chi phí |
| Thấp | `npm run lint` lỗi sẵn có: 139 lỗi trong `src/`, 290 lỗi do eslint quét `.claude/worktrees/` |

## Kết quả kiểm gần nhất

2026-11-11:
- Từ `backend/`: `.\venv\Scripts\python.exe -m pytest tests` → 938 passed, 14 skipped
  (1 cảnh báo Starlette về `httpx`).
- `widget-backend` `npm test` → 22 pass.
- Từ root: `npm run build` đạt; `npm run lint` lỗi sẵn có (429 lỗi).

## Bước tiếp theo

1. Quyết định phiên bản FastAPI tối thiểu.
2. Chạy backend với Supabase thật: `/health/db`, một lượt chat, kiểm dòng `chat_history`,
   lease trên khóa dòng thật.
3. Xác thực và ownership cho GET history (service key hoặc tài khoản; test cho cặp
   session/token khớp và không khớp).
4. Chống xử lý trùng theo `Idempotency-Key`.
5. Ghi usage thật vào `chat_history`; quyết định kiểu `retrieved_chunk_ids`.
6. Định nghĩa `/health/db` là readiness hay chẩn đoán; trả non-2xx có chủ đích; kiểm schema
   các cột `chat_history` bắt buộc.
7. Xử lý hoặc tách baseline lỗi lint frontend; loại `.claude/worktrees/` khỏi eslint.
