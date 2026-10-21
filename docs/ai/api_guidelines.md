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
- `GET /chatbot/sessions/{session_id}/history`: tải lịch sử chatbot của một
  session đã lưu.
- `POST /learning-knowledge`: chỉ khi `LEARNING_API_ENABLED=true` (xem bên dưới).
- `GET/POST /support-chat/sessions` và
  `GET /support-chat/sessions/{session_id}/messages`: đọc/tạo hội thoại CRM
  cho giao diện học tri thức, cùng feature flag.

## Support chat history

Các endpoint này dùng `public.support_chat_test_sessions` và
`public.history_support_chat`. History được lưu một message mỗi row với
`message_no`, `sender_role` (`user` hoặc `staff`) và `message_text`; backend
luôn trả theo thứ tự `message_no`.

- `GET /support-chat/sessions` trả danh sách session mới nhất trước.
- `POST /support-chat/sessions` nhận `{ "product_models": ["F86"] }` và trả
  session vừa tạo (`201`).
- `GET /support-chat/sessions/{session_id}/messages` trả `{session_id,
  messages}` hoặc `404 session_not_found`.

Các endpoint chưa có authentication/ownership và chỉ được bật rõ ràng bằng
`LEARNING_API_ENABLED=true`.

`GET /chatbot/sessions/{session_id}/history` trả:

```json
{
  "session_id": "…",
  "messages": [
    {
      "id": "…",
      "session_id": "…",
      "query_origin": "Câu hỏi",
      "answer": "Câu trả lời",
      "status": "completed",
      "created_at": "…"
    }
  ]
}
```

Endpoint này đọc các trạng thái đã lưu (`completed`, `blocked`, `error`) để
phục hồi lịch sử UI. Session không có history trả `404 session_not_found`;
database lỗi trả `503 database_unavailable`.

Khi chạy local, đặt `LEARNING_API_ENABLED=true` trong `backend/.env` rồi khởi
động lại backend. Khi chạy Docker Compose, đặt biến này trong file `.env` ở
repository root; Compose sẽ truyền biến vào container backend. Nếu không bật
flag, FastAPI không đăng ký các route support-chat và trả `404`.

`POST /learning-knowledge` (`backend/app/modules/learning_ai/router.py`) chỉ
được include khi `LEARNING_API_ENABLED=true` (mặc định tắt) vì chưa có xác thực.

## `POST /learning-knowledge`

Chạy bước nạp hội thoại CRM từ `public.history_support_chat` → prefilter →
privacy (regex + Ollama). Segmenter/Extractor và lưu job **chưa** được nối; response
là kết quả chuẩn bị, không phải tri thức đã tạo.

Request (schema version `"1.0"`, field lạ bị từ chối):

```json
{"schema_version": "1.0", "session_id": "uuid", "retry_failed": false}
```

`retry_failed` được nhận nhưng chưa có tác dụng cho tới khi có bảng job.

Response `200` (`application/json`, header `X-Request-ID`). Chỉ có text **đã che**,
text gốc không bao giờ được trả về:

```json
{
  "schema_version": "1.0",
  "request_id": "…",
  "session_id": "…",
  "status": "ready",
  "reason": null,
  "source_id": "…",
  "checker_model": "qwen2.5:7b-instruct",
  "redaction_applied": true,
  "pii_types_detected": ["person_name", "phone"],
  "flags_by_locator": {"m4": ["pricing"]},
  "unverified_findings": 0,
  "residual_redactions": 0,
  "units": [{"locator": "m1", "role": "customer", "text": "Em là [PERSON_1], gọi em [PHONE_1]"}]
}
```

`status="skipped"` kèm `reason` (`no_customer_message`, `no_staff_message`,
`greeting_only`, `too_short`) và các trường privacy rỗng.

Lỗi trả `{"detail": {"code", "message", "request_id"}}` với message tổng quát:

| HTTP | `code` | Khi nào |
|---|---|---|
| 404 | `session_not_found` | Session không có row nào |
| 422 | (FastAPI) | `session_id` không phải UUID, sai `schema_version`, field lạ |
| 503 | `privacy_provider_not_configured` | Bật route nhưng thiếu `OLLAMA_BASE_URL`/`OLLAMA_MODEL` |
| 503 | `privacy_check_unavailable` | Ollama lỗi, sai schema hoặc không xác nhận đọc đủ message |
| 503 | `database_unavailable` | Không đọc được hội thoại |
| 500 | `internal_error` | Lỗi không mong đợi |

Lý do chi tiết (cửa sổ nào lỗi, loại exception) chỉ ghi log server, không trả client.

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
- Support-chat history endpoints chỉ được enable cùng `LEARNING_API_ENABLED` và
  chưa có ownership; client legacy `/chats` không phải contract backend hiện tại.
- Retrieval/tools chưa được nối vào active response flow.
- Lượt chỉ có chitchat/out_of_scope/handoff trả câu cố định (một chunk SSE)
  không qua LLM; các lượt khác stream từ provider qua `AnswerComposer`, dựa trên
  kết quả task của execution plan. SSE contract không đổi. Output strict của
  analyzer có thêm `pending_answer` (v3.1, nội bộ). Task `retrieve` chưa có handler nên luôn `failed`
  (`handler_not_configured`). Không viết tài liệu hoặc test như thể RAG đã hoàn
  thiện.
