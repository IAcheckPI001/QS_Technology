# Nền tảng chat dùng chung (chat-platform)

Phần của lượt chat dùng chung cho [website-qa](../website-qa/README.md) và
[crm-agent](../crm-agent/README.md): khởi động, xác thực service key, session, lease, ghi
history, trace, health. Trạng thái ở [STATE.md](STATE.md), lịch sử ở [LOG.md](LOG.md). Bản mô
tả trước 2026-11-11: [LOG-archive-2026-11-11.md](LOG-archive-2026-11-11.md).

## Ba thành phần khi chạy

```text
Trình duyệt (widget src/chatbot)
  └─ cookie HttpOnly qs_visitor, qs_chat_session ─▶ widget-backend/ (Node, :8787)
       └─ Bearer qsk_… (key kênh website) + {session_id, message} ─▶ dịch vụ AI (:8000) POST /chat/website
CRM backend ─ Bearer qsk_… (key kênh crm) + {user_id, session_id, crm_access_token?, message} ─▶ POST /chat/crm
Support Workspace (trình duyệt) ─▶ GET /chatbot/... (chưa xác thực)
```

Dịch vụ AI chỉ xác thực service key và không biết khách website.

## Startup

`backend/app/main.py`: cấu hình logging, tạo FastAPI app, CORS, include
`api/v1/router.py`, bọc ngoài cùng bằng `RequestContextMiddleware` (request ID, access log có
`outcome`). Lifespan tạo `OpenAIProvider` và `Retriever` khi có `OPENAI_API_KEY`, dựng
`AgentRunner` khi `CRM_CHAT_FLOW=agent`, dựng pipeline privacy khi `LEARNING_API_ENABLED`.
Router không tự khởi tạo provider hay repository.

## Một lượt chat (phần dùng chung)

```text
RequestContextMiddleware (request_id) → dependency: RequestContext, ServiceAuthService (key đúng kênh), Idempotency-Key
 → router parse schema kênh (WebsiteChatIn / CRMChatIn); CRM: principal.acting_for(user_id)
 → SessionAccessService: tạo session của principal hoặc dùng lại session cùng chủ, cùng kênh (khác → 404)
 → SessionTurnLease (session đã có): UPDATE nguyên tử chat_sessions.turn_lease_until; đang chạy → 409 session_busy
 → ChatbotService.stream_reply: luồng website-qa hoặc crm-agent
 → HistoryRepository ghi chat_history (completed | error; blocked, cancelled ghi bằng session riêng)
 → routers/sse.py: delta…, done {request_id, session_id} | error; header X-Session-ID
 → giải phóng lease, đóng trace (log chat_trace, lưu chat_traces khi bật)
```

| Vùng | File | Vai trò |
|---|---|---|
| App, middleware | `main.py`, `api/middleware/request_context.py`, `core/request_context.py`, `core/logging.py` | Request ID, access log, log stdout có `[request_id]` |
| Route | `chatbot/routers/chat.py`, `sse.py`, `workspace.py`; `api/v1/health.py` | `POST /chat/*`, ánh xạ lỗi SSE, GET Support Workspace, health |
| Dependency | `chatbot/dependencies.py` | Service, repository, auth theo kênh, `Idempotency-Key` |
| Service | `chatbot/services/chat_service.py`, `session_access.py`, `service_auth.py` | Điều phối lượt, session + lease, xác thực key |
| Repository | `chatbot/repositories/history_repository.py`, `chat_session_repository.py`, `trace_repository.py` | `chat_history`, `chat_sessions`, `chat_traces` |
| Service key | `core/security/service_key.py`, `chatbot/service_keys_cli.py` | Băm, cấp, thu hồi key theo kênh |
| Tracing | `core/tracing.py` | Cây span trong tiến trình, chỉ metadata |
| DB | `db/engine.py`, `session.py`, `health.py`, `db/models/` | Engine, session, model ORM |
| Cấu hình | `core/config.py` | Một `Settings` cache dùng chung |

## Contract

[api_guidelines.md](../../api_guidelines.md): "Request ID", "Xác thực theo kênh",
"`POST /chat/website` và `POST /chat/crm`", "Response và SSE contract", "Support chat history"
(gồm `/trace`).

## Bất biến

- Session chỉ dùng lại khi principal (`principal_type`, `subject_id`, `tenant_id`,
  `acting_user_id`) và kênh khớp, chưa revoked/expired; UUID khác → 404 `session_not_found`.
- Transaction của request **không** UPDATE dòng `chat_sessions` của phiên đã có: lease chạy
  trên connection riêng và sẽ bị chính khóa dòng chặn. Lệnh lease đặt `lock_timeout = 3s`.
  Triệu chứng khi vi phạm (sự cố 2026-10-30): mọi lượt trên phiên đã có treo ~30 giây tới
  `statement_timeout`, widget-backend trả 502. Test dùng fake nên không tái hiện được khóa
  dòng; nguyên nhân khác cần xét: phiên bản FastAPI (STATE), cạn pool kết nối DB.
- Lease được giải phóng khi stream kết thúc vì bất kỳ lý do gì (shield trước cancel của
  anyio); tự hết hạn sau `CHAT_TURN_LEASE_S` (phải lớn hơn `AGENT_TURN_TIMEOUT_S`).
- Context chỉ đọc history `completed`; `blocked`, `cancelled` ghi bằng session DB riêng, commit
  ngay. `conversation_state` hỏng field nào thì bỏ field đó, không reset toàn bộ.
- Trace và log chỉ chứa metadata: không có nội dung tin nhắn, prompt, argument/output tool,
  câu trả lời hay `crm_access_token`. Ngoại lệ duy nhất (2026-11-11) là audit `crm_query`, nằm sau `CRM_QUERY_AUDIT_LOG` (mặc định tắt):
  - ghi argument và body query vào logger riêng `app.crm_query.audit`;
  - không ghi vào trace;
  - xem [crm-agent README](../crm-agent/README.md#giám-sát-query-llm-dựng-crm_query).
- Số liệu tổng hợp hay UUID giả chỉ dùng trong fixture test, không bao giờ thành số đo
  production.

## Cấu hình

| Biến | Mặc định | Tác dụng |
|---|---|---|
| `DATABASE_URL` | bắt buộc | |
| `DATABASE_POOL_MODE`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW`, `DATABASE_POOL_RECYCLE` | `session`, 5, 5, 1800 | Cân với số lượt agent × tool song song × task retrieve |
| `CHAT_TURN_LEASE_S` | 120 | |
| `CHAT_TRACE_PERSIST`, `CHAT_TRACE_MAX_SPANS` | `false`, 500 | Bật cần `backend/sql/chat_traces.sql` |
| `CORS_ORIGINS`, `CORS_ALLOW_CREDENTIALS`, `TRUST_PROXY_REQUEST_ID`, `LOG_LEVEL` | localhost, `false`, `false`, `INFO` | Xem [deploy-rules.md](../../rules/deploy-rules.md) |

SQL áp tay (`backend/sql/`): `chat_sessions.sql`, `service_keys.sql`,
`chat_history_workspace.sql`, `chat_traces.sql`; thứ tự ở deploy-rules.md.

## Test

```powershell
# từ backend/
.\venv\Scripts\python.exe -m pytest tests\chatbot tests\api
```

Test riêng: `test_chat_routes`, `test_session_access`, `test_service_key`, `test_chat_history`,
`test_history_api`, `test_cancelled_turn`, `test_state_loading`, `test_tracing`, `test_config`,
`tests/api/test_cors.py`, `test_request_context_middleware.py`.

## Log runtime

- Một dòng `http_request_finished` mỗi request (outcome, thời gian).
- Một dòng `chat_trace` mỗi lượt; `public.chat_traces` khi bật; đọc qua
  `GET /chatbot/sessions/{id}/trace`.
- `public.chat_history` là audit của mọi lượt (`status`, token và chi phí ước tính,
  `retrieval_snapshot`).
