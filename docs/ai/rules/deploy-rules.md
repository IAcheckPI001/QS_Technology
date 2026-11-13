# Quy tắc deploy (deploy-rules)

Cập nhật: 2026-11-11

**Hạ tầng deploy chưa chốt** (quyết định của Toma, 2026-11-11). File này chỉ gồm quy tắc
không phụ thuộc hạ tầng, rút từ code hiện có. Runbook theo hạ tầng (lệnh build, nơi chạy,
rollback cụ thể) bổ sung khi đã chốt. Các mục đánh dấu *(chưa có)* là khoảng trống, không
phải quy trình đang chạy.

## Thành phần triển khai

| Thành phần | Nguồn | Ghi chú |
|---|---|---|
| Dịch vụ AI | `backend/Dockerfile` (python:3.12-slim, `uvicorn app.main:app`, cổng 8000) | Image chỉ chép `app/`; `backend/.dockerignore` loại `doc_ingest`, test và venv |
| widget-backend | `widget-backend/` (Node.js ≥ 22, không dependency, cổng 8787) | Giữ service key; phải đặt cùng domain với trang web, bật `COOKIE_SECURE=true` |
| Frontend | `npm run build` (Vite), `vercel.json` rewrite SPA | Biến `VITE_*` bị đóng gói vào bundle trình duyệt |
| Database | Supabase Cloud | SQL áp thủ công, xem DR-04 |

`doc_ingest` là tool offline, không deploy cùng dịch vụ AI.

## Quy tắc

| ID | Quy tắc | Căn cứ trong code |
|---|---|---|
| DR-01 | Mọi cấu hình đi qua biến môi trường khai báo trong `backend/app/core/config.py`. Thêm biến mới thì cập nhật `.env.example` và bảng bên dưới trong cùng thay đổi. | `Settings` |
| DR-02 | Không đưa secret vào image, bundle frontend, log hay tài liệu. Token trong biến `VITE_*` chỉ dùng cho môi trường kiểm thử. | `widget-backend/README.md` |
| DR-03 | Cờ thử nghiệm giữ giá trị mặc định (tắt) trên production cho tới khi có quyết định bật ghi trong [decisions.md](../decisions.md). | TR-16, bảng cờ bên dưới |
| DR-04 | Áp SQL trong `backend/sql/` lên Supabase **trước** khi deploy code cần nó. Mọi file phải idempotent. Ghi ngày áp vào `LOG.md` của luồng liên quan. | Chú thích đầu mỗi file SQL |
| DR-05 | Không mở công khai route chưa có xác thực: `/chatbot/conversations`, `/chatbot/sessions/{id}/history`, `/chatbot/sessions/{id}/retrieval`, `/chatbot/sessions/{id}/trace` luôn được mount; phải chặn ở tầng mạng hoặc reverse proxy. | `chatbot/routers/workspace.py:1`, `routers/__init__.py` |
| DR-06 | Route kiểm thử `POST /api/chat/crm` của widget-backend không bật trên production (không đặt `CHATBOT_CRM_API_KEY`): `user_id` không được xác thực. | `widget-backend/README.md` |
| DR-07 | `CORS_ORIGINS` phải liệt kê đúng origin production; giá trị mặc định chỉ có localhost. Header request mới của frontend phải thêm vào `allow_headers`. | `config.py`, `main.py`, `backend/tests/api/test_cors.py` |
| DR-08 | Chỉ đặt `TRUST_PROXY_REQUEST_ID=true` khi reverse proxy luôn ghi đè `X-Request-ID`. | `main.py` |
| DR-09 | Trước deploy phải chạy đủ validation trong [AGENTS.md](../../../AGENTS.md) và ghi kết quả. Test backend hiện không chạy trong CI nên phải chạy tay. | `.github/workflows/ci-cd.yml` |
| DR-10 | Sau deploy kiểm `GET /health`, `GET /health/db`, rồi một lượt hỏi đáp qua widget (SSE có `delta` và `done`). | `api/v1/health.py`, `routers/sse.py` |
| DR-11 | Rollback kênh CRM từ agent về pipeline bằng `CRM_CHAT_FLOW=pipeline`, không cần đổi code. | `config.py:42` |

## Biến môi trường của dịch vụ AI

| Biến | Bắt buộc | Mặc định | Ghi chú |
|---|---|---|---|
| `DATABASE_URL` | có | không có | Thiếu thì ứng dụng không khởi động |
| `OPENAI_API_KEY` | có, cho chat | rỗng | Rỗng thì không tạo provider; chat trả `provider_not_configured` |
| `CORS_ORIGINS` | có, trên production | localhost:5173 | Danh sách cách nhau bằng dấu phẩy |
| `CRM_CHAT_FLOW` | không | `agent` | `pipeline` để rollback (DR-11). Mặc định `agent` là ngoại lệ tạm thời trong lúc kiểm thử (D-006); xem lại trước production |
| `CRM_REPORT_ENABLED` | không | `false` | Bật thì bắt buộc `CRM_API_BASE_URL` và múi giờ IANA hợp lệ; thử nghiệm |
| `CRM_TOOLS` | không | `query` | `query` (LLM tự dựng query mọi bảng CRM), `catalog` hoặc `both` (D-005). Khi bật tool CRM, dữ liệu nghiệp vụ kể cả liên hệ khách hàng đi tới nhà cung cấp LLM |
| `AGENT_MODEL` | không | rỗng (= `OPENAI_MODEL`) | Model riêng cho vòng lặp agent kênh CRM; luồng website và stage phân tích giữ `OPENAI_MODEL`. Chọn theo `evals/compare_agent_models.py`. Khi bật tool CRM, đặt `gpt-4.1-mini` (quyết định 2026-11-12: guide `crm_query` được tinh chỉnh cho model này; gpt-4o-mini sai nhiều hơn ở hiểu tham số và ngữ cảnh qua lượt) |
| `AGENT_REASONING_EFFORT` | không | rỗng | Chỉ cho model suy luận (`gpt-5…`, `o3…`): `none`/`minimal`/`low`/`medium`/`high` tuỳ model |
| `AGENT_MAX_COMPLETION_TOKENS` | không | 1200 | Token đầu ra mỗi bước LLM của agent; model suy luận tính cả token suy nghĩ, đặt khoảng 4000 |
| `CRM_QUERY_AUDIT_LOG` | không | `false` | Khi bật, log server (logger `app.crm_query.audit`) chứa giá trị filter và query gửi CRM, có thể là PII. Chỉ bật có thời hạn để đánh giá query, và giới hạn người được xem log |
| `LEARNING_API_ENABLED` | không | `false` | Route chưa có xác thực; bật cần `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |
| `CHAT_TRACE_PERSIST` | không | `false` | Bật cần áp `backend/sql/chat_traces.sql` trước; không có retention tự động |
| `DATABASE_POOL_MODE`, `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW` | không | `session`, 5, 5 | Chọn theo kiểu kết nối Supabase |
| `LOG_LEVEL` | không | `INFO` | Log ra stdout, mỗi dòng có `request_id` |

Danh sách đầy đủ (giới hạn agent, tham số retrieval, giá token): `backend/app/core/config.py`.
Biến của widget-backend: `widget-backend/.env.example` và `widget-backend/README.md`.

## SQL áp thủ công

Repo chưa có migration tool. Thứ tự cho môi trường mới:

| Thứ tự | File | Cần trước khi |
|---|---|---|
| 1 | `chat_sessions.sql` | Deploy `POST /chat/website`, `POST /chat/crm` |
| 2 | `service_keys.sql` | Cấp service key bằng `python -m app.modules.chatbot.service_keys_cli create ...` |
| 3 | `chat_history_workspace.sql` | Deploy API workspace (`/chatbot/...`) |
| 4 | `doc_chunks.sql` | Dùng retrieval (`match_doc_chunks`) |
| 5 | `chat_traces.sql` | Đặt `CHAT_TRACE_PERSIST=true` |
| 6 | `doc_chunks_v2.sql` | Nạp chunk từ luồng chunking và retrieval v2 (D-009); tạo song song `doc_chunks`, cài `unaccent` vào schema `extensions`. Đã áp 2026-11-13 (Toma, SQL editor); áp lại cùng ngày cho tham số R-2/R-4 của `match_doc_chunks_v2` |
| riêng | `migrate_product_models_crm.sql` | Chuyển dữ liệu một lần; chạy từng bước, có bước xem trước |

Bảng gốc `public.chat_history` đã có sẵn trên Supabase; repo *(chưa có)* file tạo bảng này.

## Khoảng trống cần xử lý khi chốt hạ tầng

- `docker-compose.yml` dựng `postgres:17` và Elasticsearch mà code không dùng, không có
  widget-backend, và không truyền các biến `CRM_*`, `AGENT_*`, `CHAT_TRACE_*`.
- `Dockerfile` ở root chạy `npm run dev` (Vite dev server), không phải bản build production.
- CI (`.github/workflows/ci-cd.yml`) chỉ build frontend, trigger nhánh `main` trong khi
  nhánh chính là `master`; không chạy lint, không chạy pytest, không có bước deploy.
- *(chưa có)* quy trình rollback image, sao lưu trước khi áp SQL, retention cho `chat_traces`.
- *(chưa có)* rate limit theo khách ở widget-backend; Idempotency-Key mới được nhận và
  lưu, chưa chống xử lý trùng.
