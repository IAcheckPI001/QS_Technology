# API guidelines

## Phạm vi và lớp API

Backend dùng FastAPI tại `backend/app/`. API transport chỉ chịu trách nhiệm
định nghĩa route, parse/validate request, dependency wiring, HTTP/SSE response
và ánh xạ lỗi. Business flow nằm trong service/stage; truy cập database nằm
trong repository; provider-specific LLM code nằm trong provider layer.

Các route hiện được include từ `backend/app/api/v1/router.py`:

- `GET /health`: kiểm tra process đang chạy, trả `{"status": "ok"}`.
- `GET /health/db`: chạy database connectivity check, trả trạng thái database.
- `POST /chat/website/visitor`: cấp/làm mới visitor token cho khách website.
- `POST /chat/website`: chat của khách website (visitor token), trả
  `text/event-stream`.
- `POST /chat/crm`: chat từ CRM backend (server-to-server, service key), trả
  `text/event-stream`.
- `GET /chatbot/sessions/{session_id}/history`: tải lịch sử chatbot của một
  session đã lưu.
- `GET /chatbot/conversations`: danh sách hội thoại chatbot và số liệu tổng
  cho màn Lịch sử hội thoại của Support Workspace.
- `GET /chatbot/sessions/{session_id}/retrieval`: snapshot chunk truy xuất của
  lượt gần nhất có chunk, cho màn Kết quả chunk.
- `POST /ai/learning`: chỉ khi `LEARNING_API_ENABLED=true` (xem bên dưới).
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
      "created_at": "…",
      "updated_date": "…",
      "channel": "website",
      "model": "gpt-4o-mini",
      "input_tokens": 12,
      "output_tokens": 80,
      "total_tokens": 92,
      "cost_usd": 0.00005,
      "latency_ms": 1800
    }
  ]
}
```

`channel` là `website` hoặc `crm`. Token/cost hiện là **ước tính** từ câu hỏi
và câu trả lời (`count_tokens`), chưa gồm prompt/context gửi LLM và embedding.

Endpoint này đọc các trạng thái đã lưu (`completed`, `blocked`, `error`,
`cancelled`) để
phục hồi lịch sử UI. Session không có history trả `404 session_not_found`;
database lỗi trả `503 database_unavailable`.

### `GET /chatbot/conversations`

Query: `search` (tối đa 200 ký tự, khớp `query_origin` hoặc `model` của lượt
mới nhất) và `status` (`completed` | `blocked` | `error` | `cancelled`; giá trị khác trả
`422`). Mỗi session một dòng, mới nhất trước:

```json
{
  "conversations": [
    {
      "session_id": "…",
      "model": "gpt-4o-mini",
      "product_models": ["F86"],
      "ticket_id": "TK-1048",
      "last_query": "Câu hỏi cuối",
      "channel": "crm",
      "created_at": "tin nhắn đầu tiên",
      "updated_date": "tin nhắn cuối",
      "status": "completed",
      "total_tokens": 120,
      "cost_usd": 0.0001
    }
  ],
  "total": 1,
  "conversation_count": 128,
  "handoff_count": 12,
  "total_tokens": 54000,
  "total_cost_vnd": 1320.5
}
```

`status`, `product_models` (`conversation_state.last_models`) và `ticket_id`
lấy từ lượt mới nhất. `conversation_count`, `handoff_count` (số session có
lượt `conversation_state.mode != "bot"`), `total_tokens` và `total_cost_vnd`
(`cost_usd × USD_TO_VND_RATE`) tính trên toàn bảng, không theo bộ lọc.
Database lỗi trả `503 database_unavailable`.

### `GET /chatbot/sessions/{session_id}/retrieval`

Trả snapshot `chat_history.retrieval_snapshot` của lượt gần nhất có chunk:

```json
{
  "session_id": "…",
  "history_id": "…",
  "query": "Máy F86 chạy xung bị lệch",
  "model": "gpt-4o-mini",
  "product_models": ["F86"],
  "highest_score": 0.92,
  "latency_ms": 124,
  "total_tokens": 92,
  "retrieval_status": "ok",
  "chunks": [
    {
      "rank": 1,
      "score": 0.92,
      "content": "…",
      "domain": "technical_docs",
      "scopes": ["installation", "maintenance"],
      "control_interface": ["pulse_train"],
      "spec_attributes": ["io", "max_axis"],
      "page_start": 4,
      "page_end": 26,
      "page_label": "page 4 - 26"
    }
  ]
}
```

Chunk xếp theo `score` giảm dần. `domain`/`scopes`/`control_interface`/
`spec_attributes` là metadata của chính chunk trong `doc_chunks`, không phải
filter của truy vấn. `latency_ms` là thời gian retrieval lâu nhất trong lượt.
`retrieval_status` tổng hợp các task retrieve của lượt: `ok`, `no_hits` (không
chunk nào qua ngưỡng), `partial_error` / `error` (một phần / mọi task tra cứu lỗi
embedding hoặc database), `incomplete` (task chưa chạy xong), `not_applicable`
(lượt không tra cứu); `null` với bản ghi cũ. Snapshot trong DB còn có
`retrieval_tasks: [{task_id, status, error_code, no_hits, fallback}]`. Lỗi tra
cứu **không** được báo cho khách (LLM trả lời mềm, history vẫn `completed`);
trường này là dấu vết để vận hành và Support Workspace theo dõi.
Không có snapshot trả `404 retrieval_not_found`; database lỗi trả
`503 database_unavailable`.

Khi chạy local, đặt `LEARNING_API_ENABLED=true` trong `backend/.env` rồi khởi
động lại backend. Khi chạy Docker Compose, đặt biến này trong file `.env` ở
repository root; Compose sẽ truyền biến vào container backend. Nếu không bật
flag, FastAPI không đăng ký các route support-chat và trả `404`.

`POST /ai/learning` (`backend/app/modules/learning_ai/router.py`) chỉ
được include khi `LEARNING_API_ENABLED=true` (mặc định tắt) vì chưa có xác thực.

## `POST /ai/learning`

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

## Request ID

`RequestContextMiddleware` (`backend/app/api/middleware/request_context.py`) bọc
ngoài cùng app: sinh `request_id` (UUID) cho mỗi HTTP request, gắn vào
`request.state.request_id`, context var dùng cho log (`[request_id]` trong mọi
dòng log) và header response `X-Request-ID` (kể cả 500). ID client gửi chỉ được
dùng khi `TRUST_PROXY_REQUEST_ID=true` (reverse proxy luôn ghi đè header) và
khớp `^[A-Za-z0-9._-]{8,64}$`. Mọi `request_id` trong body lỗi và SSE trùng
với header. Dòng log `http_request_finished` có `outcome=` do route ghi
(`ok`, mã lỗi SSE/HTTP, hoặc `client_disconnected`) vì SSE luôn trả HTTP 200.

## Xác thực theo kênh

Channel do endpoint quyết định, không lấy từ body. Principal
(`PrincipalContext`) chỉ do auth dependency dựng
(`backend/app/modules/chatbot/dependencies.py`), không bao giờ từ body.

- **Website (guest)**: client gọi `POST /chat/website/visitor` (không body)
  để nhận `{"schema_version": "1.0", "token", "token_type": "Bearer",
  "expires_at"}`. Token là JWT HS256 do server ký bằng `VISITOR_TOKEN_SECRET`
  (`sub` = `guest_id`, TTL `VISITOR_TOKEN_TTL_SECONDS`, mặc định 7 ngày). Gửi kèm
  `Authorization: Bearer <token>` còn hợp lệ thì được làm mới cùng `guest_id`;
  thiếu/sai/hết hạn thì nhận `guest_id` mới. Chat gửi
  `Authorization: Bearer <token>`.
- **CRM (service)**: CRM backend gửi `Authorization: Bearer qsk_<key_id>_<secret>`.
  Key cấp cho từng hệ thống tích hợp, chỉ lưu ở server CRM (`.env`), **không**
  đưa xuống JavaScript trình duyệt và không bật CORS cho luồng này. Chatbot tra
  `key_id` trong `public.service_keys` (chỉ lưu SHA-256 của secret), so sánh hằng
  thời gian, kiểm tra `revoked_at`/`expires_at` và `disabled_at` của integration,
  rồi dựng principal `service`:

  | Trường | Nguồn |
  |---|---|
  | `subject_id` | `service_integrations.id` (giữ nguyên khi xoay vòng key) |
  | `tenant_id` | `service_integrations.tenant_id` (hiện cố định `qs_technology`) |
  | `credential_id` | `service_keys.id` (= `key_id`; audit/thu hồi) |
  | `acting_user_id` | `user_id` trong body |
  | `roles`, `scopes` | rỗng (chưa dùng) |

  `user_id` là giá trị CRM khẳng định sau khi tự xác thực nhân viên; Chatbot
  tin vì tin key. Key bị lộ thì có thể mạo danh mọi nhân viên của integration
  đó: thu hồi và cấp key mới (`python -m app.modules.chatbot.service_keys_cli
  create|revoke`, chạy từ `backend/`). Áp dụng `backend/sql/service_keys.sql`
  trước khi deploy.

## `POST /chat/website` và `POST /chat/crm`

Header:

- `Authorization: Bearer <token>`: bắt buộc.
- `Idempotency-Key: <uuid>`: tùy chọn. Client tạo một key cho mỗi tin nhắn mới
  và giữ nguyên khi retry chính request đó. **Hiện chỉ được lưu vào
  `chat_history.idempotency_key`; backend chưa chống xử lý trùng.**

Body (schema version `"1.0"`, field lạ bị bỏ qua):

```json
{
  "schema_version": "1.0",
  "session_id": "optional-uuid",
  "message": {"text": "Câu hỏi của người dùng"},
  "client_context": {
    "locale": "vi",
    "timezone": "Asia/Ho_Chi_Minh",
    "page_url": "https://example.com"
  }
}
```

Body của `/chat/crm` khác website (field lạ, kể cả `client_context` và
`context_refs`, bị bỏ qua):

```json
{
  "schema_version": "1.0",
  "user_id": "employee_456",
  "session_id": null,
  "message": {"text": "Hướng dẫn xử lý lỗi trên bộ điều khiển CNC F86"}
}
```

- `user_id`: bắt buộc, 1–128 ký tự sau khi strip.
- `session_id`: `null`/bỏ trống = hội thoại mới (nút "Cuộc trò chuyện mới");
  lượt sau gửi giá trị từ event `done`. Không phải bí mật: chỉ dùng lại được
  khi session cùng integration **và** cùng `user_id`.

- `message.text`: 1–4.000 ký tự sau khi strip.
- `message_id` do server sinh (trùng `chat_history.id`); `message_id` hay
  `channel` client gửi bị bỏ qua.
- `session_id`: phải là UUID (sai định dạng → 422). Thiếu → server tạo session
  mới thuộc principal hiện tại (`public.chat_sessions`). Có → chỉ dùng lại khi
  session cùng principal (`principal_type`, `subject_id`, `tenant_id`,
  `acting_user_id`), cùng
  kênh, chưa revoked/expired; mọi trường hợp khác trả `404 session_not_found`
  (không tiết lộ session tồn tại). Session cũ chỉ có trong `chat_history`
  (trước khi có `chat_sessions`) cũng nhận 404: client xóa `session_id` và bắt
  đầu hội thoại mới.
- `client_context.timezone`: tên dạng IANA (`Area/City`), tối đa 64 ký tự;
  `page_url` tối đa 2.048 ký tự; `locale` dạng `vi` hoặc `vi-VN`.
- `branch` chưa dùng (luôn `null`); CRM không có branch tra cả
  `crm-technical` và `crm-sale`.

Lỗi trước khi mở stream trả JSON `{"detail": {"code", "message", "request_id"}}`:

| HTTP | `code` | Khi nào |
|---|---|---|
| 401 | `unauthorized` | Thiếu/sai/hết hạn visitor token (kèm `WWW-Authenticate: Bearer`) |
| 401 | `invalid_service_key` | `/chat/crm`: thiếu, sai định dạng, không tồn tại, sai secret, bị thu hồi, hết hạn key, hoặc integration bị disable. Cùng một body cho mọi lý do; lý do chỉ ghi log `Service key rejected reason=... key_id=...` (kèm `WWW-Authenticate: Bearer`) |
| 404 | `session_not_found` | `session_id` không thuộc principal/kênh, bị thu hồi hoặc hết hạn |
| 422 | `invalid_idempotency_key` | `Idempotency-Key` không phải UUID |
| 422 | (FastAPI) | Body sai schema |
| 503 | `visitor_auth_not_configured` | Chưa đặt `VISITOR_TOKEN_SECRET` |
| 503 | `provider_not_configured` | Chưa đặt `OPENAI_API_KEY` |
| 503 | `database_unavailable` | Không đọc/tạo được session, hoặc không tra được service key (không quy thành 401) |

Áp dụng `backend/sql/chat_sessions.sql` trên Supabase trước khi deploy.

## Response và SSE contract

Route trả `StreamingResponse` với:

- `Content-Type: text/event-stream`;
- `Cache-Control: no-cache, no-transform`;
- `X-Request-ID` do middleware tạo và expose qua CORS.

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

- Lỗi HTTP trước khi stream: xem bảng ở mục trên.
- SSE `request_blocked`: request bị SecurityStage chặn.
- SSE `context_error`: context/pruning không chuẩn bị được.
- SSE `analysis_error`: không phân tích/lập kế hoạch/dựng prompt trả lời được
  (`AnalysisError`, `ExecutionError`, `AnswerCompositionError`: timeout hoặc lỗi
  provider ở bước phân tích, output sai schema, plan không hợp lệ). Xảy ra trước
  khi có `delta`.
- SSE `provider_error`: lỗi trong phần xử lý provider/stream câu trả lời, hoặc
  lỗi không phân loại.

Mọi lỗi sau khi context đã nạp (analysis, execution, compose, stream) đều được
ghi `chat_history` với `status='error'`, kèm phần câu trả lời đã stream (nếu có).
Nếu client ngắt kết nối giữa lượt (Starlette đóng generator hoặc huỷ task), lượt
được ghi `status='cancelled'` kèm phần câu trả lời đã stream, bằng session DB
riêng và không cập nhật `conversation_state`; log middleware có
`outcome=client_disconnected`.

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
  `backend/app/main.py`. CORS cho phép header request `Content-Type`, `Accept`,
  `Authorization`, `Idempotency-Key`, `X-Request-ID`, `X-CSRF-Token` và expose
  `X-Request-ID`. Header request mới mà frontend gửi phải được thêm vào
  `allow_headers`, nếu không preflight trả `400 Disallowed CORS headers` và trình
  duyệt chặn request (kiểm bằng `backend/tests/api/test_cors.py`). Đây là danh
  sách được phép, không phải header bắt buộc.
- History được ghi vào Supabase `public.chat_history`: `completed`, `error`
  (đã kiểm chứng commit sau khi stream bằng test, FastAPI 0.143), `blocked` hoặc
  `cancelled` (hai trạng thái sau commit ngay bằng session riêng).
  `normalized_query` lưu câu hỏi đã chuẩn hóa tiếng Việt.
- `client_context.locale` chỉ là nguồn dự phòng cho ngôn ngữ trả lời: ưu tiên
  ngôn ngữ do analysis phát hiện, rồi ngôn ngữ của phiên. Câu cố định chỉ có
  `vi`/`en`; ngôn ngữ khác được sinh qua LLM. Output strict của analyzer có thêm
  `language` (v3.3, nội bộ).
- Support-chat history endpoints chỉ được enable cùng `LEARNING_API_ENABLED` và
  chưa có ownership; client legacy `/chats` không phải contract backend hiện tại.
- Retrieval đã nối ở mức kiểm thử (xem architecture.md bước 8); tools chưa có.
- Lượt chỉ có chitchat/out_of_scope/handoff trả câu cố định (một chunk SSE)
  không qua LLM; các lượt khác stream từ provider qua `AnswerComposer`, dựa trên
  kết quả task của execution plan. Output strict của analyzer có thêm
  `pending_answer` (v3.1, nội bộ) và `model_dependency` (`general` |
  `model_specific`, v3.2, nội bộ); `RetrievalPlan.answer_mode` có thêm `general`. Task `retrieve` chạy hybrid
  search trên `doc_chunks`; lỗi task nội bộ mới là `retrieval_error` (không lộ ra
  SSE). Schema nội bộ `RetrievalRequest` có thêm `product_scope_mode`,
  `control_interface`, `spec_attributes`; `RetrievalSubQueryResult` có `hits`
  (`ChunkHit`, gồm `assets`); `RetrievalFilters.collections` không còn bắt buộc.
  SSE chưa có event sources/assets. Không viết tài liệu hoặc test như thể RAG đã
  hoàn thiện (chưa rerank, tham số chưa tối ưu, chưa kiểm thử với Supabase thật).
