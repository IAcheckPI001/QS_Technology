# API guidelines

## Phạm vi và lớp API

Backend dùng FastAPI tại `backend/app/`. API transport chỉ chịu trách nhiệm
định nghĩa route, parse/validate request, dependency wiring, HTTP/SSE response
và ánh xạ lỗi. Business flow nằm trong service/stage; truy cập database nằm
trong repository; provider-specific LLM code nằm trong provider layer.

Các route hiện được include từ `backend/app/api/v1/router.py`:

- `GET /health`: kiểm tra process đang chạy, trả `{"status": "ok"}`.
- `GET /health/db`: chạy database connectivity check, trả trạng thái database.
- `POST /chatbot`: nhận request website và trả `text/event-stream`.

`backend/app/modules/learning_ai/router.py` hiện chưa được include, vì vậy
không được coi là public API đang hoạt động. Route scaffold
`POST /learning-knowledge` trả HTTP 501 cho tới khi ingestion, learning service
và persistence được triển khai. Khi include, phải bổ sung schema version và
response contract theo hướng dẫn này.

## `POST /chatbot`

Request body dùng schema version `"1.0"`:

```json
{
  "schema_version": "1.0",
  "session_id": "optional-uuid",
  "message": {
    "message_id": "client-message-id",
    "text": "Câu hỏi của người dùng"
  },
  "client_context": {
    "locale": "vi",
    "timezone": "Asia/Ho_Chi_Minh",
    "page_url": "https://example.com"
  }
}
```

`message.text` là nội dung bắt buộc, tối đa 4.000 ký tự theo Pydantic schema.
`session_id` là giá trị định danh hội thoại do client lưu; không phải
credential/authorization. UUID hợp lệ chỉ được dùng lại khi đã có history,
còn thiếu, sai hoặc chưa biết sẽ được backend cấp UUID mới.

## Response và SSE contract

Route trả `StreamingResponse` với:

- `Content-Type: text/event-stream`;
- `Cache-Control: no-cache, no-transform`;
- `X-Request-ID` do backend tạo và expose qua CORS.

Các event hiện có:

```text
event: delta
data: {"text":"..."}

event: done
data: {"request_id":"...", "session_id":"..."}

event: error
data: {"code":"...", "message":"...", "request_id":"..."}
```

Client phải đọc theo SSE framing, nhận nhiều `delta`, chỉ coi request thành
công khi nhận `done`, và xử lý `error` theo `code`. Các mã lỗi chính:

- HTTP `503` `provider_not_configured`: provider chưa được cấu hình.
- HTTP `503` `database_unavailable`: không khởi tạo được session.
- SSE `request_blocked`: request bị SecurityStage chặn.
- SSE `context_error`: context/pruning không chuẩn bị được.
- SSE `provider_error`: lỗi trong phần xử lý provider/stream.

Thông báo trả client phải tổng quát; không trả detector rule, stack trace,
secret hoặc nội dung log nội bộ.

## Quy tắc triển khai endpoint

1. Schema request/response phải explicit, versionable và đặt trong module
   tương ứng; không dùng `dict` tùy ý để thay thế contract.
2. Router không gọi trực tiếp LLM provider, không chứa business rule và không
   truy cập database ngoài dependency wiring.
3. Dependency dùng để cung cấp service/repository và infrastructure cần thiết.
4. Service điều phối stages; stage trả typed decision/domain result, không tự
   tạo HTTP response.
5. Repository là ranh giới duy nhất cho persistence. History context chỉ đọc
   các record `status='completed'`; record blocked được audit riêng.
6. Lỗi phải được phân loại và ánh xạ rõ ràng. Không nuốt exception hoặc trả
   success-shaped fallback.
7. Thay đổi schema, SSE event, error code hoặc status code là thay đổi API và
   phải cập nhật tài liệu/test liên quan.
8. Secrets và cấu hình triển khai lấy từ environment/settings; không ghi vào
   source hoặc response.

## Trạng thái và giới hạn hiện tại

- CORS, OpenAI provider lifecycle và database session được cấu hình ở
  `backend/app/main.py`.
- History được ghi vào Supabase `public.chat_history`: `completed`, `error`
  (nếu error transaction được commit) hoặc `blocked`.
- Không có history-read endpoint đang được enable; client legacy `/chats` không
  phải contract backend hiện tại.
- Retrieval/tools chưa được nối vào active response flow.
- Provider final answer streaming hiện chưa chạy end-to-end; service đang trả
  các chunk mẫu sau bước analysis. Không viết tài liệu hoặc test như thể RAG
  và provider answer streaming đã hoàn thiện.
