# Frontend requirements (phân tích hiện trạng)

> Phân tích ngày 2026-11-17 trên `feature/deploy_ai_service` @ `0636646` (API v0.2.0).
> Mục đích: đầu vào cho thiết kế lại frontend (Support Workspace): khung chat kiểm thử,
> quản lý phiên bản chunk tài liệu, lịch sử hội thoại, thống kê chi phí, service và
> service key, các nghiệp vụ khác.

## Trạng thái (cập nhật 2026-11-17)

- **Giai đoạn: giao diện version 1 đã duyệt** (Toma 2026-11-18): toàn bộ mock desktop và
  điện thoại ở **artifact version 47** là bản chuẩn để dựng frontend. Kế hoạch triển khai:
  **mục 18**. Chưa có code frontend hay backend nào theo tài liệu này.
- Mock: canvas "Support Workspace mock" (artifact claude.ai, riêng tư) — đăng nhập, lịch sử hội
  thoại (chốt v1), chi tiết hội thoại, 4 màn trace, kho tài liệu, xem và duyệt tài liệu,
  service keys, tài khoản. Màn kho tài liệu / duyệt **giữ nguyên** cho tới khi luồng backend
  thay đổi. Version 32 đã sửa các lỗi kiểm thử ở mục 16 (mobile, trạng thái rỗng, xác nhận,
  thông báo, bàn phím). Version 33 thêm hàng "Bản điện thoại" gồm 8 màn 390×844 (mục 17).
- Tên hiển thị: **QS AI Workspace**, logo và màu nâu/vàng QS Technology (Q21, version 34).
- Sidebar desktop đứng yên khi cuộn, thu gọn được, khối tài khoản ghim đáy (Q22, version 36).
- Chi tiết hội thoại ưu tiên thông tin nghiệp vụ, thông số kỹ thuật thu gọn (Q23, version 38).
- Lý do sửa đoạn không bắt buộc; lịch sử bản dài được thu gọn (Q24, version 39).
- Màn duyệt tài liệu có mục lục kiểu Google Docs (nhảy tới) và tìm kiếm (Q25, version 40).
- Tải thêm 25 hội thoại / 20 lượt; tìm và lọc chạy trên toàn bộ dữ liệu ở server (Q26).
- Màn Service keys đổi thành "Khóa dịch vụ AI", chữ dễ hiểu, tên trùng tự thêm -1/-2 (Q27, version 45).
- Quyết định đã chốt: Q1–Q27 (mục 13). Kế hoạch backend cho màn tài liệu: mục 15.
- **Còn mở**:
  1. Lưu `conversation_state.last_models` theo từng lượt (cột `product_models` mỗi lượt) hay chỉ
     sửa tạm đọc lượt `completed` gần nhất (mục M2/Q16).
  2. Quy tắc duyệt theo mức rủi ro (Chặn / Cần xem / Lấy mẫu / Tự duyệt), đoạn số liệu có luôn
     phải người xem, tỉ lệ lấy mẫu — đổi contract C2/D-009.
  3. Quy tắc duyệt hình, đoạn nhiều hình, OCR lỗi, kế thừa khi có phiên bản mới (đã đề xuất,
     chưa ghi thành quyết định).
  4. Lưu người duyệt / thời điểm / ghi chú (đề xuất có; đã đưa vào B6).
  5. Contract API phiên bản tài liệu của CRM; nơi dựng lại `embed_text` sau khi sửa trên web.
  6. File PDF trên CRM (`F54 - Operation Guide.pdf`) khác bản doc-ingest đã xử lý — CRM sẽ cập
     nhật lại tài liệu.
  7. Thao tác "Bỏ duyệt" / "Bật lại" thêm trong mock (mục 16).

## 0. Phương pháp và quy ước

Mọi yêu cầu truy vết từ code (route → dependency/service → repository → ORM/SQL), không
suy ra từ tên API. Khi tài liệu luồng và code lệch, tin code và ghi chỗ lệch. Phần backend
chưa có ghi là khoảng trống, không thiết kế như đã sẵn sàng.

| Nhãn | Nghĩa |
|---|---|
| **Có** | Endpoint chạy được, trình duyệt gọi được |
| **S2S** | Có, nhưng chỉ server tích hợp gọi được (service key); trình duyệt đi qua `widget-backend` |
| **Cờ** | Chỉ khi `LEARNING_API_ENABLED=true`; tắt thì 404 |
| **CLI** | Chỉ có lệnh dòng lệnh / script, không có API |
| **Domain** | Logic thuần + test, không API, không bảng |
| **Không** | Chưa tồn tại |

## 1. Tóm tắt

1. **Ba nhóm người gọi, ba mức tin cậy** (`flows/chat-platform/README.md`):
   - Khách website → `widget-backend` (Node, :8787, cookie HttpOnly) → `POST /chat/website`
     bằng service key.
   - CRM backend → `POST /chat/crm` bằng service key + `user_id` do CRM khẳng định.
   - **Support Workspace (trình duyệt) → `GET /chatbot/...` không xác thực, không ownership,
     luôn được mount** (DR-05: phải chặn ở tầng mạng). Mọi màn quản trị mới sẽ thừa hưởng
     lỗ hổng này cho tới khi có đăng nhập.
2. **Không có tài khoản người dùng, role hay permission.** Xác thực duy nhất là service key
   của hệ thống tích hợp. `principal.roles/scopes` luôn rỗng.
3. **Service key chỉ quản lý được bằng CLI** (`service_keys_cli create|revoke`). Không có API
   liệt kê integration/key, không có `last_used_at`, quota, rate limit, scope.
4. **Chi phí trong lịch sử là ước tính sai lệch có hệ thống**: token đếm từ text câu hỏi và
   câu trả lời (không gồm prompt, context, embedding, tool), nhân đơn giá gpt-4o-mini cho
   mọi model (`chat_service.py:383`), kể cả lượt lỗi không gọi được LLM (mục 12). Usage thật có trong trace (`summary`) nhưng chỉ khi
   `CHAT_TRACE_PERSIST=true` và không có API tổng hợp.
5. **Phiên bản chunk có ở bảng mới `doc_chunks_v2`** (`doc_version`, `review_status`
   `draft|approved`, `source_run`, `is_active`, `loaded_at`) nhưng **chat production vẫn đọc
   bảng cũ `doc_chunks`**, bảng v2 chỉ eval dùng, và không có API nào cho cả hai bảng.
6. **Chat kiểm thử từ trình duyệt** chỉ đi được qua `widget-backend`: `/api/chat`
   (website) và `/api/chat/crm` (chỉ kiểm thử; `user_id` không xác thực).
7. **Support Workspace hiện có ba lỗi luồng** (mục 2.2): mở hội thoại từ "Lịch sử" ra màn
   ticket sai nguồn dữ liệu; màn "Kết quả chunk" đọc session từ localStorage không còn ai
   ghi; endpoint trace chưa có UI.

## 2. Hiện trạng frontend

| Hạng mục | Thực tế |
|---|---|
| Stack | React 18 + Vite 7, JavaScript/JSX, axios, react-router-dom 7, react-i18next, react-markdown, lucide-react |
| Route | `src/App.jsx`: chỉ `/` → `SupportWorkspace` |
| API client | `api.service.js`: axios `baseURL = VITE_API_URL` (dev: `http://localhost:8000`) cho `GET /chatbot/*`, `/support-chat/*`, `/ai/learning` |
| Widget | `chatbot.service.js`: `fetch` tới `VITE_WIDGET_API_URL` + `/api/chat…` (cùng origin, Vite proxy `/api` → :8787), gửi `Idempotency-Key` mới mỗi tin |

### 2.1 Màn hình đang có

| Màn | Thành phần | Dữ liệu |
|---|---|---|
| Hỗ trợ ticket | `pages/Chat.jsx` | `GET/POST /support-chat/sessions`, `GET …/messages`, `POST /ai/learning` (Cờ) |
| Kết quả chunk | `SupportWorkspace.jsx` `ChunkResults` | `GET /chatbot/sessions/{id}/retrieval` |
| Lịch sử hội thoại | `SupportWorkspace.jsx` `Conversations` | `GET /chatbot/conversations?search&status` |
| Widget nổi | `chatbot/Chatbot.jsx` | `GET /api/chat/history`, `POST /api/chat` hoặc `/api/chat/crm` khi `VITE_CHATBOT_CHANNEL=crm` |

### 2.2 Lỗi luồng và sai lệch (đã đối chiếu code)

| # | Hiện trạng | Bằng chứng | Ảnh hưởng |
|---|---|---|---|
| F1 | Chọn một dòng ở "Lịch sử hội thoại" chuyển sang "Hỗ trợ ticket" và gọi `GET /support-chat/sessions/{id}/messages` với `session_id` của **chat_history** | `SupportWorkspace.jsx:303`, `Chat.jsx:62` | Hai bảng khác nhau → luôn 404 "chưa có trong hệ thống hỗ trợ ticket". Không màn nào hiển thị nội dung hội thoại chatbot dù có `GET /chatbot/sessions/{id}/history` |
| F2 | Session đang xem khởi tạo từ `localStorage.chatbot_session_id` | `SupportWorkspace.jsx:19,36` | Không code nào còn ghi key này (session nằm ở cookie HttpOnly của widget-backend) → "Kết quả chunk" rỗng nếu chưa chọn từ lịch sử |
| F3 | `GET /chatbot/sessions/{id}/trace` không có UI | grep `src/` | Không xem được span, usage thật, lỗi tool |
| F4 | Nhãn `completed` hiển thị "Đang mở" | `SupportWorkspace.jsx:23` | Sai nghĩa: `completed` là lượt trả lời xong, không phải ticket mở |
| F5 | `EventSource('/intro-stream')` | `Chat.jsx:87` | Backend không có route → 404 mỗi lần mở |
| F6 | Ô soạn tin ở màn ticket | `Chat.jsx` | Không có API thêm message support-chat → UI không chức năng |
| F7 | `MAX_REQUEST_LENGTH = 1500` | `Chat.jsx:13`, `Chatbot.jsx:8` | Backend cho 4.000 |
| F8 | "Tổng chi phí" và "Số hội thoại" | `workspace.py:113-117` | Tính trên **toàn bảng**, không theo `search/status`; bảng lại bị lọc → hai số không khớp nhau |
| F9 | Code cũ (blog, auth, session, contact, services; `getChats`, `checkSession`, …) | `src/pages`, `src/auth`, `src/hooks` | Không route nào dùng, gọi API không tồn tại |

## 3. API endpoints

CORS: `allow_methods = GET, POST, OPTIONS`; header cho phép gồm `Authorization`,
`Idempotency-Key`, `X-CSRF-Token`; `allow_credentials` theo `CORS_ALLOW_CREDENTIALS`
(mặc định `false`); expose `X-Request-ID` (`main.py:80-94`). API ghi dùng
`PUT/PATCH/DELETE` phải sửa CORS.

### 3.1 Dịch vụ AI (`backend/`, :8000)

| Method | Path | Nhãn | Nguồn |
|---|---|---|---|
| GET | `/health`, `/health/db` | Có | `api/v1/health.py` |
| POST | `/chat/website` | S2S | `chatbot/routers/chat.py:50` |
| POST | `/chat/crm` | S2S | `chat.py:81` |
| GET | `/chatbot/conversations` | Có, **không xác thực** | `routers/workspace.py:80` |
| GET | `/chatbot/sessions/{id}/history` | Có, không xác thực | `workspace.py:47` |
| GET | `/chatbot/sessions/{id}/retrieval` | Có, không xác thực | `workspace.py:121` |
| GET | `/chatbot/sessions/{id}/trace?history_id` | Có, không xác thực; rỗng nếu `CHAT_TRACE_PERSIST=false` | `workspace.py:170` |
| GET/POST | `/support-chat/sessions` | Cờ | `learning_ai/router.py` |
| GET | `/support-chat/sessions/{id}/messages` | Cờ | như trên |
| POST | `/ai/learning` | Cờ | như trên |

Contract chi tiết (request, response, mã lỗi): [api_guidelines.md](api_guidelines.md).
Điểm frontend cần biết thêm, đã đối chiếu code:

- `/chatbot/conversations`: `search` ≤ 200 ký tự khớp `query_origin` hoặc `model` **của lượt
  mới nhất** (không tìm theo `ticket_id` dù placeholder UI ghi "Tìm ticket");
  `status ∈ completed|blocked|error|cancelled` (khác → 422). **Không phân trang**, `total`
  = số dòng trả về. Không lọc theo kênh, thời gian, model sản phẩm.
- `/history`: mọi trạng thái, có `channel`, `model`, token, `cost_usd`, `latency_ms`; 404
  `session_not_found` (body không có `request_id`).
- `/retrieval`: chỉ snapshot của **lượt mới nhất có chunk**; không chọn được lượt khác.
  `retrieval_status ∈ ok|no_hits|partial_error|error|incomplete|not_applicable|null`.
  Các khóa `retrieval_tasks`, `agent_steps`, `invalid_citations` có trong DB nhưng endpoint
  chưa trả. 404 `retrieval_not_found`.
- `/trace`: cây span theo `parent_id`, chỉ metadata; `summary` có token thật. 404
  `trace_not_found`; bảng chưa tạo → 503.

### 3.2 `widget-backend` (Node, :8787)

| Route | Mô tả |
|---|---|
| `POST /api/chat` | SSE từ `/chat/website`; session trong cookie `qs_chat_session`; hết hạn thì tự mở hội thoại mới một lần |
| `GET /api/chat/history` | `{messages}` của hội thoại hiện tại |
| `POST /api/chat/crm` | Chỉ kiểm thử; bật khi có `CHATBOT_CRM_API_KEY`; `user_id` do trình duyệt gửi, **không xác thực** |
| `POST /api/chat/reset` | Xoá cookie session (hội thoại mới), 204 |

Lỗi riêng: `400 invalid_json|invalid_request`, `403 origin_not_allowed`,
`413 payload_too_large` (>16 KB), `502 chat_unavailable|ai_service_unreachable`; 422/503 của
dịch vụ AI chuyển tiếp nguyên mã.

### 3.3 SSE (cả hai kênh)

`delta {text}` (0..n), `done {request_id, session_id}`, `error {code, message, request_id}`.
Header `X-Session-ID`. Mã lỗi SSE: `request_blocked`, `context_error`, `analysis_error`,
`agent_error` (chỉ CRM agent), `provider_error`. Kênh CRM chạy agent trả câu trả lời cuối
trong **một** `delta`. Không có event nguồn/citation/ảnh/tiến trình.

## 4. Business logic

### 4.1 Lượt chat (phần dùng chung, `flows/chat-platform/README.md`)

```text
RequestContextMiddleware (request_id) → ServiceAuthService: key đúng kênh
 → SessionAccessService: tạo session của principal, hoặc dùng lại khi cùng principal + kênh
 → lease theo phiên (409 session_busy nếu lượt trước chưa xong)
 → website-qa (pipeline) | crm-agent (agent khi CRM_CHAT_FLOW=agent)
 → chat_history: completed | error; blocked, cancelled ghi bằng session riêng
 → SSE; nhả lease; đóng trace (chat_traces nếu bật)
```

- Website: security → context → làm rõ → analysis → retrieve (`doc_chunks` cũ) → stream.
  Handoff là scaffold (không ticket). `[S#]` đánh lại mỗi lượt.
- CRM agent: tool `product_docs_ask`; khi `CRM_REPORT_ENABLED=true` thêm `crm_schema`,
  `crm_query` (đọc dữ liệu CRM theo token nhân viên, có thể chứa PII khách và được lưu vào
  `chat_history`).
- Ngắt kết nối giữa lượt → `cancelled`, giữ phần đã stream.

### 4.2 Service key (`services/service_auth.py`, `core/security/service_key.py`)

Định dạng `qsk_<key_id>_<secret>`; DB chỉ lưu SHA-256; so sánh hằng thời gian; từ chối khi
không tồn tại, sai secret, `revoked_at`, `expires_at` quá hạn, integration `disabled_at`
(mọi lý do → cùng `401 invalid_service_key`); sai kênh → `403 service_key_channel_mismatch`.
Xoay vòng = cấp key mới cho integration rồi thu hồi key cũ; `subject_id` (integration) giữ
nguyên nên session cũ vẫn dùng được. CLI đặt được hạn (`--expires-in-days`) nhưng không có
lệnh disable integration (`disabled_at` chỉ sửa tay trong DB).

### 4.3 Chunk và phiên bản

- `doc_chunks` (cũ, production): khóa `(doc_id, chunk_index)`, `is_active`; không version.
- `doc_chunks_v2` (D-009): khóa `(doc_id, doc_version, chunk_key)` và
  `(doc_id, doc_version, chunk_index)`; `chunk_role parent|child|standalone` (D-008: chỉ con và
  độc lập được tìm); `review_status draft|approved` (retriever chỉ dùng `approved`, trừ khi
  eval tắt); `source builder|manual`, `source_run`, `embedding_model`, `loaded_at`.
  Hiện có F54 296, F86 Installation 23, catalog 37 chunk, **đều draft**.
- Nạp: `doc_ingest` (CLI, venv riêng) → `chunking_loader/load_ingest_run.py`. Duyệt chunk
  (cổng 2b/2c, verdict) chạy bằng file JSON và CLI, chưa có API/UI.

### 4.4 Học tri thức (Cờ)

`POST /ai/learning`: nạp hội thoại CRM → prefilter → privacy (regex + Ollama, fail-closed);
không lưu kết quả, chưa tạo tri thức. Vòng đời review `KnowledgeRecord` (draft →
pending_review → approved/rejected; approved bất biến, sửa bằng revision mới) chỉ là
Domain ([flows/learning/STATE.md](flows/learning/STATE.md)).

## 5. Database (bảng frontend chạm tới)

| Bảng | Vai trò | SQL |
|---|---|---|
| `chat_history` | Một lượt hỏi–đáp: `status`, `channel`, `model`, token/chi phí ước tính, `latency_ms`, `conversation_state`, `retrieval_snapshot`, `idempotency_key`, `created_at`, `updated_date` | `chat_history_workspace.sql` (cột thêm) |
| `chat_sessions` | Chủ phiên: `principal_type`, `subject_id`, `tenant_id`, `acting_user_id`, `channel`, `expires_at`, `revoked_at`, `turn_lease_until` | `chat_sessions.sql` |
| `chat_traces` | Trace mỗi lượt (`history_id`, `outcome`, `duration_ms`, `trace` jsonb); không retention | `chat_traces.sql` |
| `service_integrations`, `service_keys` | Integration (kênh, tenant, `disabled_at`) và key (hash, `expires_at`, `revoked_at`) | `service_keys.sql` |
| `doc_chunks`, `doc_chunks_v2` | Chunk tài liệu cũ / mới | `doc_chunks.sql`, `doc_chunks_v2.sql` |
| `support_chat_test_sessions`, `history_support_chat` | Hội thoại CRM mẫu cho learning | Supabase quản lý |

Quan hệ: `service_integrations 1─n service_keys`; `chat_sessions.subject_id` =
`service_integrations.id` (không FK); `chat_history.session_id` ↔ `chat_sessions.id` (không
FK); `chat_traces.history_id` ↔ `chat_history.id` (không FK); `doc_chunks_v2.parent_id` tự
tham chiếu. `chat_history` **không** lưu `credential_id`/integration → không thống kê được
theo key hay theo integration (chỉ theo `channel`).

## 6. Authentication

| Đối tượng | Cơ chế | Trạng thái |
|---|---|---|
| Hệ thống tích hợp | `Authorization: Bearer qsk_…` | Có |
| Khách website | Cookie HttpOnly do `widget-backend` quản lý; dịch vụ AI không biết khách | Có |
| Nhân viên CRM | `user_id` do CRM khẳng định (tin theo key); `crm_access_token` chuyển tiếp cho tool | Có, ủy quyền tin cậy |
| Người dùng Support Workspace | — | **Không**: không login, access/refresh token, session |

## 7. Authorization và phạm vi dữ liệu

- Session: chỉ dùng lại khi khớp `principal_type, subject_id, tenant_id, acting_user_id` và
  kênh; sai → 404 (không tiết lộ tồn tại).
- Kênh: key chỉ gọi được endpoint đúng kênh.
- Dữ liệu CRM: phạm vi do CRM quyết theo token nhân viên (`crm_forbidden` khi thiếu quyền).
- `roles`, `scopes`, `required_scope` của tool là điểm gắn, chưa dùng.
- **GET Support Workspace**: không kiểm tra gì; `/chatbot/conversations` liệt kê mọi session
  của mọi kênh, kể cả câu trả lời có thể chứa PII khách CRM.

## 8. Validation frontend phải phản chiếu

| Trường | Rule | Nguồn |
|---|---|---|
| `message.text` | strip, 1–4.000 ký tự | `schemas/default.py` |
| `session_id` (chat) | UUID hoặc null; sai định dạng → 422 | `schemas/channels/` |
| `client_context.locale` | `vi` hoặc `vi-VN` | như trên |
| `client_context.timezone` | IANA `Area/City`, ≤ 64 | như trên |
| `client_context.page_url` | ≤ 2.048 | như trên |
| `user_id` (CRM) | 1–128 sau strip | `channels/crm.py` |
| `crm_access_token` | 1–4.096, tùy chọn | như trên |
| `Idempotency-Key` | UUID | `dependencies.py` |
| `search` (conversations) | ≤ 200 | `workspace.py:83` |
| `status` (conversations) | `completed|blocked|error|cancelled` | `schemas/history.py:8` |
| `product_models` (support-chat) | `F54, F86, F86E, F10T, 6AH, 6AHE, 6AV, 6AVE, 10iV, 10iVE` | `learning_ai/schemas/api.py` |
| Body widget-backend | ≤ 16 KB | `widget-backend/README.md` |

## 9. Error handling

Dạng lỗi: `{"detail": {"code", "message", "request_id"?}}`; 422 FastAPI là
`{"detail": [{loc, msg, type}]}`. Luôn hiển thị `request_id` (body hoặc `X-Request-ID`).

| Mã | Ở đâu | Frontend phải |
|---|---|---|
| `session_not_found` (404) | chat | Bỏ session, mở hội thoại mới (widget-backend đã tự làm một lần) |
| `session_busy` (409) | chat | Báo đang trả lời lượt trước, khoá gửi, cho gửi lại sau |
| `invalid_idempotency_key` (422) | chat | Lỗi lập trình |
| `provider_not_configured`, `database_unavailable` (503) | mọi nơi | Báo tạm thời, cho thử lại |
| `chat_unavailable`, `ai_service_unreachable` (502) | widget-backend | Báo dịch vụ chat không sẵn sàng |
| `origin_not_allowed` (403), `payload_too_large` (413) | widget-backend | Lỗi cấu hình / nội dung quá dài |
| SSE `request_blocked` | chat | Hiển thị `message` như câu trả lời của bot |
| SSE `context_error`, `analysis_error`, `agent_error`, `provider_error` | chat | Giữ phần đã stream (nếu có), đánh dấu lỗi, cho gửi lại |
| `retrieval_not_found`, `trace_not_found` (404) | workspace | Trạng thái rỗng, không phải lỗi |
| `incomplete_stream`, `invalid_stream_event` | client | Coi là lỗi lượt |
| Learning: `privacy_provider_not_configured`, `privacy_check_unavailable`, `internal_error` | `/ai/learning` | Xem api_guidelines |
| 404 không `code` ở `/support-chat`, `/ai` | cờ tắt | Ẩn khu vực học tri thức |

## 10. Yêu cầu theo module

### M1. Lịch sử hội thoại — làm được, cần sửa F1, F4, F8

- Danh sách từ `/chatbot/conversations` (lọc `status`, tìm theo câu hỏi/model).
- **Chi tiết hội thoại**: màn riêng đọc `/chatbot/sessions/{id}/history` (bong bóng hỏi–đáp,
  trạng thái từng lượt, `channel`, `model`, `latency_ms`, token/chi phí ước tính), có lối sang
  "Kết quả chunk" và "Trace" của cùng session. Không dùng màn support-chat cho việc này.
- Ghi rõ chỉ số tổng tính trên toàn bộ dữ liệu, không theo bộ lọc.
- Chưa có: phân trang, lọc kênh/thời gian, xuất file, xoá (B2).

### M2. Thống kê và chi phí — một phần

- Có: số hội thoại, số handoff (session có `mode != bot`), tổng token, tổng chi phí VND
  (`cost_usd × USD_TO_VND_RATE`, mặc định 26.000).
- Phải gắn nhãn "ước tính" cho token/chi phí lấy từ `chat_history` (mục 1.4). Usage thật chỉ
  hiển thị ở màn trace từng lượt.
- Chưa có: chuỗi thời gian, theo kênh/model/integration/key, usage thật tổng hợp (B3, B4).

### M3. Kết quả chunk và trace — làm được, cần sửa F2, F3

- Chunk: hiển thị `retrieval_status` (hiện UI bỏ qua), bảng chunk, điểm, trang.
- Trace: cây span theo `parent_id`, `outcome`, `summary` (llm_calls, tool_calls, lỗi, token
  thật), `tool_errors`, `error_detail`. Báo rõ khi server tắt `CHAT_TRACE_PERSIST`.
- Chọn lượt cụ thể: trace có `history_id`; retrieval chưa có (B5).
- Hiển thị cho người không kỹ thuật: mỗi span có nhãn tiếng Việt, tên kỹ thuật in nhỏ bên dưới;
  lượt lỗi có hộp tóm tắt "thất bại ở bước nào" lấy từ span lỗi gốc (span lỗi không có con lỗi).
  Nhãn (tên span lấy từ `span("…")` trong code, 2026-11-17):

  | Span | Nhãn |
  |---|---|
  | `chat.request` | Toàn bộ lượt trả lời |
  | `session.resolve`, `session.lease_acquire`, `session.lease_release` | Mở phiên hội thoại; Giữ phiên (chặn gửi trùng); Nhả phiên |
  | `stage.security`, `stage.context_load`, `stage.prune`, `stage.clarification` | Kiểm tra an toàn nội dung; Đọc lịch sử; Rút gọn lịch sử; Kiểm tra câu hỏi làm rõ đang chờ |
  | `stage.analysis`, `llm.chat_json` | Phân tích câu hỏi; Gọi AI để phân tích |
  | `stage.catalog_lookup`, `stage.execution`, `embedding`, `db.fetch_chunks` | Tra catalog sản phẩm; Tra cứu tài liệu; Chuyển câu hỏi thành dạng tìm kiếm; Lấy đoạn tài liệu |
  | `stage.compose`, `llm.stream_chat`, `llm.chat_text` | Soạn câu trả lời; AI viết câu trả lời |
  | `agent.run`, `agent.wait_slot`, `llm.chat_tools` (bước N) | Trợ lý CRM xử lý; Chờ lượt xử lý; AI chọn bước tiếp theo (bước N) |
  | `tool.product_docs_ask`, `tool.crm_schema`, `tool.crm_query`, `query.fetch`, `http.crm_*` | Tra tài liệu sản phẩm; Đọc cấu trúc dữ liệu CRM; Truy vấn dữ liệu CRM; Lấy dữ liệu; Gọi API CRM |
  | `history.write`, `handoff.transfer` | Lưu lịch sử; Chuyển nhân viên |

  Tên span mới chưa có nhãn thì hiện nguyên tên kỹ thuật.
- Kiểm live: trace lượt lỗi ghi đủ chuỗi lỗi (`chat.request` = `analysis_error` →
  `stage.analysis` error → `llm.chat_json` error `RateLimitError`). Thiếu: chỉ có
  `error_type` của exception, không có mã lỗi của nhà cung cấp, nên **không phân biệt được
  "hết credit" (`credit_balance_exhausted`) với "gọi quá nhanh"**, cả hai đều HTTP 429 (B5).
- Cách đọc trace theo trạng thái lượt (đối chiếu code + DB thật 2026-11-17):

  | Trạng thái lượt | Dấu hiệu trong trace | UI phải làm |
  |---|---|---|
  | Hoàn tất | `outcome=ok`; có thể kèm `tool_errors` ở root và span tool lỗi (DB thật: lượt CRM 12/11 hoàn tất nhưng 5/6 lần gọi tool lỗi, CRM trả 404, vượt `tool_call_limit`) | Hộp cảnh báo "đã trả lời nhưng công cụ lỗi" khi có `tool_errors` hoặc `failed_tool_calls > 0`; `deduplicated` là trung tính, không tính lỗi |
  | Lỗi | `outcome` = mã SSE (`analysis_error`…); span lỗi gốc = span lỗi không có con lỗi | Hộp lỗi nêu bước lỗi gốc |
  | Bị chặn | `outcome=request_blocked`, root `flow=blocked`; **span `stage.security` có `status=ok`**, chặn nằm ở thuộc tính `action=block` + `rule_ids`, `categories`, `highest_severity`; không có span LLM, context | Nhận diện chặn bằng `action=block`, **không** bằng status span; hiện nhóm luật đã dịch, không có nội dung tin nhắn |
  | Đã ngắt | `outcome=client_disconnected`; span đang chạy lúc ngắt = `cancelled`, span chưa đóng = `unfinished`; root có `deltas`, `first_delta_ms` | Hộp "mất kết nối giữa lượt", số đoạn đã gửi; nêu rõ `conversation_state` không cập nhật |

- Trace chỉ có khi server bật `CHAT_TRACE_PERSIST`: DB thật có trace cho 1/8 hội thoại hoàn tất
  và 1/5 hội thoại lỗi (các lượt cũ trước khi bật). Trạng thái "không có trace" (404
  `trace_not_found`) là trường hợp thường gặp, không phải lỗi.
- Danh sách hội thoại không biết lượt "hoàn tất" nào có tool lỗi (`tool_errors` chỉ ở trace,
  `agent_steps` trong `retrieval_snapshot` chưa trả ra) → B5.
- DB thật chưa có lượt `blocked` hay `cancelled`; hai màn đó trên mock dựng theo code.

### M4. Khung chat kiểm thử — làm được qua widget-backend

- Website: `/api/chat`, `/api/chat/history`, `/api/chat/reset`.
- CRM: `/api/chat/crm` với `user_id`, `crm_access_token` nhập tay; **chỉ ở môi trường kiểm
  thử** vì `user_id` không xác thực. Hiển thị rõ đang ở kênh nào.
- Sau mỗi lượt, lấy `session_id` từ `done` để mở chunk/trace của lượt vừa chạy (hiện widget
  không đưa giá trị này ra ngoài).
- Không có: chọn model/prompt/routing version khi chat (chỉ có trong eval CLI).

### M5. Quản lý tài liệu và phiên bản chunk — bị chặn

Ràng buộc dữ liệu đã có ở `doc_chunks_v2` (mục 4.3) là nền để thiết kế: một tài liệu có
nhiều `doc_version`, mỗi chunk có `review_status`, `is_active`, `source_run`, cây cha–con.
Thiếu: API liệt kê/xem/duyệt/kích hoạt chunk và phiên bản, chạy nạp/embedding, so sánh phiên
bản, chuyển chat sang `doc_chunks_v2` (B6).

Dữ liệu thật (đọc chỉ đọc 2026-11-17, `scripts/inspect_doc_chunks.py` + truy vấn asset):

- `doc_chunks` (chat production đang đọc): **3 dòng** thử. `doc_chunks_v2`: 356 dòng, **đều
  `draft`**: `f54_operation_v02` V.02 (53 cha / 150 con / 93 độc lập),
  `f86_installation_2024-04-25` (23), `qs_product_catalogue` 2026-11-14 (37, nguồn biên soạn).
- Hình: 335 asset (`bucket` `f54-docs`, `f86-docs`, `path` `<doc>/<doc>_p017_e006.png`,
  `page` = trang PDF, `printed_page` = trang in). Chunk có hình: mọi `figure`, phần lớn
  `wiring`, 32/70 `procedure`, và chunk cha `section` (gom hình của con). **Supabase Storage
  không có object nào** → ảnh chỉ nằm trong thư mục run offline (`data/ingest_runs/…/images/`),
  frontend chưa hiển thị được. PDF gốc cũng chưa lưu ở đâu online.
- Vị trí trên trang: chunk có `page_start/page_end`, `metadata.element_ids` (319/356);
  **bbox chỉ có ở `NormalizedElement`** (point, gốc trên-trái) trong file run, không vào bảng →
  highlight chính xác vùng chunk trên PDF cần doc-ingest xuất thêm `metadata.regions
  [{page, bbox}]` (B6).
- Nội dung cho người không kỹ thuật: `summary_vi` (tóm tắt tiếng Việt), `metadata.faq_vi`
  (câu hỏi chunk trả lời được, 243 chunk lá), `content` là nguyên văn tiếng Anh của PDF.

Thiết kế màn (mock 2026-11-17, "Kho tài liệu" + "Xem và duyệt"):

- Kho tài liệu (Toma chốt cấu trúc 2026-11-17): (1) thống kê **Tổng số tài liệu / Đang sử dụng
  / Chờ duyệt** (kèm số đoạn chờ duyệt); (2) vùng **Cần duyệt** ở trên: thẻ gọn trả lời 4 câu
  — tài liệu gì (tên, loại, phiên bản), cho model nào, tiến độ duyệt, việc cần làm tiếp
  ("Cần duyệt N đoạn") — nhãn "Tài liệu mới" / "Phiên bản mới", nút **Xem và duyệt**; (3) vùng
  **Đang sử dụng** ở dưới dạng bảng (tài liệu, model, phiên bản đang dùng, số đoạn, dùng từ),
  có tìm và lọc model, nút **Quản lý**. Một tài liệu có cả bản đang dùng và phiên bản mới chờ
  duyệt thì xuất hiện ở cả hai vùng. Cần API: số liệu tổng, danh sách theo trạng thái (B6).

- Thuật ngữ cho admin: chunk → **đoạn kiến thức**; chunk cha → **mục** (gom đoạn, có "Duyệt cả
  mục"); `review_status` → Chờ duyệt / Đã duyệt; `is_active` → "Tắt khỏi chatbot";
  `chunk_type`, `scopes`, `domain` dịch tiếng Việt. Trường kỹ thuật không hiển thị.
- Thẻ đoạn (Toma chốt thứ tự 2026-11-17, dữ liệu thật `doc_chunks_v2`), từ trên xuống:
  1. Loại (`chunk_type` dịch), trang **in**, trạng thái duyệt. `chunk_type` **không phải
     intent**: doc-ingest tự gán khi cắt đoạn (`build/chunker.py` `_classify`: có định nghĩa
     tham số → `parameter`; ≥ 2 bước → `procedure`; hình, ít chữ → `figure`; còn lại `overview`;
     bảng → `table`), rồi `_retype` đổi theo regex trên tiêu đề/caption/nội dung trong profile
     (`profiles/default.yaml` `chunk_type_rules` → `pinout`, `wiring`, `dimension`, `alarm`,
     `spec`). Có thể sai (vd. B0018 "operation structure" thành `wiring` do tiêu đề mục chứa
     "wiring"); chưa có bước duyệt loại. Intent (`lookup.product_info`, `guide.installation`…)
     là nhãn của **câu hỏi** do bước phân tích gán; hai bên chỉ nối qua tham số đang đo
     `p_chunk_types`/`type_boost` của `match_doc_chunks_v2` (S-04). Nhãn hiển thị:
     section Mục · procedure Hướng dẫn thao tác · parameter Tham số · alarm Mã cảnh báo ·
     table Bảng · figure Hình minh hoạ · wiring Sơ đồ đấu dây · pinout Sơ đồ chân ·
     dimension Kích thước · overview Tổng quan · spec Thông số.
  2. Tiêu đề lấy từ `section_title` (**không** có cột tiêu đề riêng; không viết lại): đoạn con
     có dạng `"<mục cha> › <tiêu đề con>"` → tiêu đề = phần sau `›` (bỏ `:` cuối), dòng phụ nhỏ
     = mục cha; đoạn độc lập dùng nguyên `section_title`. Giữ nguyên lỗi chính tả của PDF
     ("stauts", "sreen").
  3. **Nội dung gốc trích từ PDF** (`content`, tiếng Anh, `white-space: pre-wrap`): bỏ dòng đầu
     khi trùng tiêu đề; quá ~260 ký tự thì thu gọn ~5 dòng + "Xem đầy đủ (N ký tự)".
  4. **Hình trong đoạn** (`assets`): lưới 2 cột, **hiện 2 hình đầu**, còn lại sau "Xem thêm N
     hình" (F54: 16 đoạn lá có ≥ 3 hình, nhiều nhất 5 — vd. B0285); chú thích ghép theo thứ tự
     với dòng `Figure N.` trong `content`, không có thì "Hình i/n", kèm trang in. Bấm hình mở
     **xem phóng to** (lớp phủ toàn màn: hình lớn, chú thích, "i / n", trước/sau, phím Esc/←/→,
     "Mở trang này trong PDF"). Dưới lưới là "Chữ đọc được trong hình" (`figure_labels`
     `verified`, tối đa 10 + "+N", bỏ trùng); nhãn chưa xác minh hiện gạch ngang, "chatbot không
     dùng". Ảnh cần ở Supabase Storage với link có thời hạn (B6).
  5. **Bổ sung bởi AI** (khối nền tím, thứ yếu): `summary_vi`, mọi câu `faq_vi`, từ khoá
     (`keywords`, thu gọn; ẩn mục lặp mã model / số mục / tiêu đề tiếng Anh).
  6. Nút Tắt khỏi chatbot / Duyệt.
- Chunk cha (`section`, `summary_vi` null, `content` = nối các con) không hiện thành thẻ; chỉ là
  khung nhóm "Mục" với "Duyệt cả mục".
- Màn chia đôi: trái PDF từ link CRM trong trình xem của trình duyệt (Q17: mở tại `page_start`,
  không tô vùng, có nút "Mở PDF trong tab mới"), phải đoạn theo mục lục (`section_path`), lọc
  Tất cả / Chờ duyệt / Đã duyệt / Có hình; đoạn đang chọn được viền ở cột phải. Danh sách đoạn
  phân trang theo `chunk_index` (Q3).
- Chưa chốt: lưu ảnh lên Supabase Storage (link có thời hạn) — đã định hướng ở Q17, chưa có
  bước tải lên; duyệt trên web thay hay bổ sung cổng 2b/2c offline; tải PDF lên qua web (hiện
  chỉ CLI).

#### So sánh bản (diff) của đoạn — đề xuất backend (Q18)

- **Lưu**: mỗi bản là ảnh chụp đầy đủ, bất biến, trong bảng revision (`content`, `content_hash`,
  `base_revision`, nguồn, người, thời điểm, lý do). **Không lưu diff** — diff suy ra được từ hai
  bản, lưu thêm dễ lệch.
- **Tính**: khi gọi, backend so hai bản bằng `difflib.SequenceMatcher` (thư viện chuẩn Python,
  không thêm dependency): theo dòng, rồi theo từ trong dòng bị thay. Đoạn ≤ ~2.500 ký tự nên
  tính tức thì, không cần cache. Cùng hàm dùng cho so đoạn giữa hai phiên bản tài liệu (PDF bản
  cũ ↔ bản mới).
- **API** (đề xuất): `GET …/chunks/{chunk_key}/revisions` (danh sách, không kèm nội dung),
  `GET …/revisions/{n}` (nội dung), `GET …/revisions/{n}/diff?against={m|current}` →
  `{"from": 1, "to": 2, "changed_lines": 3, "hunks": [{"op": "equal|insert|delete|replace",
  "from_lines": [5, 5], "to_lines": [5, 5], "segments": [{"op": "equal", "text": "…(NC"},
  {"op": "insert", "text": ")"}]}]}`. Frontend chỉ vẽ: tô dòng theo `op`, tô chữ trong dòng
  theo `segments`. Mock hiện so cùng vị trí dòng — chỉ đúng khi không thêm/xoá dòng.

#### Đối chiếu mock ↔ luồng và DB (đọc `doc_chunks_v2` 2026-11-17)

| Thành phần trên mock | Có trong dữ liệu? | Ghi chú |
|---|---|---|
| Tổng số tài liệu, phân loại | Một phần | Đếm được từ `doc_id`, nhưng `doc_id` chứa phiên bản (`f54_operation_v02`) → mỗi phiên bản đếm thành một tài liệu |
| Đang sử dụng, "Dùng từ", phiên bản đang dùng | **Không** | Chưa có "phiên bản đang kích hoạt"; chat production đọc `doc_chunks` cũ |
| Chờ duyệt, "N đoạn cần duyệt", tiến độ | Có | Đếm `review_status`; nhưng `approved` tính lúc nạp từ file cổng offline |
| Nhãn "Tài liệu mới" / "Phiên bản mới" | **Không** | Không có lịch sử phiên bản theo một tài liệu cố định |
| Tên tài liệu | Một phần | `doc_title` = "Operation Manual (English Version)" — **không có model**, F54 và F86 trùng tên → hiển thị phải ghép model + `doc_title` |
| Loại tài liệu | Có | `doc_type`: `user_guide`, `installation_manual`, `product_catalogue` → cần bảng nhãn tiếng Việt |
| Model | Có | gộp `product_models`; catalog = F54, F86, F10T, 6AH, 6AV, 10S, 10i |
| Nạp lúc / lần nạp | Có | `loaded_at`, `source_run` |
| Nút Thêm tài liệu, đồng bộ CRM | **Không** | Chỉ CLI offline; chưa có job, chưa có API phiên bản của CRM |
| Link PDF (cách A) | **Không** | Không lưu link CRM, hash, số trang |
| Mục lục, nhóm "Mục", số đoạn/hình của mục | Có | `section_path`, `parent_id`, `assets` |
| Trang PDF / trang in | Có (F54) | `page_start`; trang in thiếu ở catalog (37/37) và 1 đoạn F86 → hiện "tr. PDF n" thay thế |
| Loại đoạn, tiêu đề, nội dung gốc, chú thích hình | Có | `chunk_type`, `section_title`, `content`; chú thích ghép từ dòng `Figure N.` (heuristic) |
| Hình, phóng to | **Không** | `assets` có đường dẫn nhưng Storage trống |
| Chữ đọc được trong hình (đã/chưa xác minh) | Có | `metadata.figure_labels[].verified` |
| Bổ sung bởi AI | Một phần | Có ở F54 (243/243 lá); **F86 (23) và catalog (37) không có** `summary_vi`/`faq_vi` → khối AI phải có trạng thái "Chưa có" |
| Từ khoá | Có | `keywords` (lẫn mã model, số mục, tiêu đề tiếng Anh) |
| Duyệt, Bỏ duyệt, Duyệt cả mục | **Không** | Không có API; kết quả duyệt nằm ở `chunk_review.json`, không có người/thời điểm trong DB |
| Tắt khỏi chatbot | Một phần | Cột `is_active` có, `match_doc_chunks_v2` lọc theo; không có API |
| Sửa nội dung, lịch sử, khôi phục, diff | **Không** | Cần bảng revision + API (Q18) |
| Lọc Tất cả/Chờ duyệt/Đã duyệt/Có hình, "8 / 243 đoạn" | Có dữ liệu, **không có API** | Cần API danh sách đoạn có lọc + phân trang (Q3) |
| Lý do cần xem (duyệt theo rủi ro) | Có tín hiệu, **chưa có trên mock** | `review_blockers`, `review_notes`, `flags` có trong `metadata` |

### M6. Service và service key — bị chặn (CLI)

Dữ liệu sẵn có: integration (`id`, `name`, `channel`, `tenant_id`, `created_at`,
`disabled_at`), key (`key_id`, `created_at`, `expires_at`, `revoked_at`). Secret chỉ hiện
**một lần** lúc tạo. Thiếu: API quản trị (liệt kê, tạo, thu hồi, disable), `last_used_at`,
thống kê theo key, và bắt buộc phải có đăng nhập quản trị trước (B1, B7).

### M7. Học tri thức từ hội thoại CRM — Cờ

Như hiện có, cần hiển thị đủ kết quả privacy (`units` đã che, `pii_types_detected`,
`flags_by_locator`, `unverified_findings`, `residual_redactions`) và bỏ ô soạn tin (F6).
Review tri thức: Domain, chưa có API.

## 11. Khoảng trống backend

| # | Khoảng trống | Chặn | Mức |
|---|---|---|---|
| B1 | Đăng nhập bằng bảng tài khoản riêng + permission theo vai trò (đợt đầu `admin`), bảo vệ mọi route Workspace kể cả GET `/chatbot/*` (mục 14) | Mọi màn quản trị | Cao, làm trước |
| B2 | Phân trang cursor cho `/chatbot/conversations` và `/history`, lọc kênh/thời gian phía server, endpoint chỉ số theo cùng bộ lọc (mục 13); thêm số câu hỏi mỗi hội thoại và tổng số câu hỏi (Q12); bộ lọc `handoff` cho kênh website (Q14); tìm kiếm theo Q15 và bộ lọc model sản phẩm (Q16) | M1, M2 | Cao |
| B3 | Ghi usage thật (từ trace) và đơn giá theo model vào `chat_history` | M2 | Trung bình |
| B4 | API thống kê theo thời gian/kênh/model; lưu `credential_id` vào history | M2, M6 | Trung bình |
| B5 | `/retrieval?history_id`; trả `retrieval_tasks`, `agent_steps`; ghi mã lỗi nhà cung cấp (vd `credit_balance_exhausted`) vào thuộc tính span LLM; cờ "có lỗi công cụ" cho lượt hoàn tất trong history/danh sách | M1, M3 | Trung bình |
| B6 | API chunk/phiên bản trên `doc_chunks_v2` (phiên bản đang kích hoạt mỗi `doc_id`, rollback, chunk phân trang offset theo `chunk_index`); bảng tài liệu (doc_id, phiên bản, link PDF trên CRM, hash, số trang) và kiểm file CRM khớp file đã xử lý (Q17); tải ảnh của chunk lên Supabase Storage + link có thời hạn; bảng revision của đoạn + API sửa/khôi phục + tạo lại embedding (Q18); bảng duyệt (người duyệt, thời điểm, ghi chú); tích hợp v2 vào chat | M5 | Cao |
| B7 | API quản trị service key, `last_used_at`, rate limit | M6 | Theo nhu cầu |
| B8 | Endpoint capability (cờ learning, trace persist, kênh CRM test) và endpoint registry model sản phẩm (Q16) | M1, M3, M4, M7 | Trung bình |

## 12. Kiểm chứng live (2026-11-17)

Preview worktree `:5174` → widget-backend `:8787` → dịch vụ AI `:8000` (checkout chính) →
Supabase thật, một câu hỏi qua widget:

- `/health/db` ok; `/chatbot/conversations` trả dữ liệu thật (có lượt CRM `gpt-4.1-mini`).
- Lượt chat: OpenAI trả 429 `credit_balance_exhausted` (B-1 của website-qa) → SSE
  `analysis_error`. Dòng `chat_history` `status=error` **được ghi** (`answer=null`,
  `model=gpt-4o-mini`, `input_tokens=14`, **`cost_usd=2e-6` dù lời gọi OpenAI thất bại**);
  `/trace` trả `outcome=analysis_error`, `summary.input_tokens=0`; `/retrieval` 404.
- Hệ quả cho frontend: chi phí ước tính tính cả lượt lỗi (thêm vào mục 1.4); widget hiển thị
  câu chung "could not be sent" thay vì `message` của `analysis_error`.

Điều kiện chạy local phát hiện khi kiểm:

- Windows: uvicorn chạy thường dùng `ProactorEventLoop`, psycopg async từ chối → mọi request
  DB trả 503. Phải chạy `uvicorn app.main:app --port 8000 --reload` (subprocess dùng
  `SelectorEventLoop`). Chưa ghi trong tài liệu chat-platform.
- Origin frontend mới phải có trong `ALLOWED_ORIGINS` của widget-backend, nếu không POST
  `/api/chat` trả `403 origin_not_allowed`.

## 13. Quyết định (Toma, 2026-11-17)

| # | Quyết định | Hệ quả |
|---|---|---|
| Q1 | Support Workspace cho admin, kỹ thuật viên, reviewer; **bắt buộc đăng nhập** | B1 là điều kiện trước khi publish; GET `/chatbot/*` phải yêu cầu phiên đăng nhập |
| Q2 | "Service" = integration gọi API chat (CRM backend, website backend) bằng service key, quản lý theo kiểu OpenAI API key | Tạo (tên, kênh, hạn), secret hiện một lần, danh sách hiện `qsk_<key_id>_…`, thu hồi; cần B7 |
| Q3 | Phiên bản chunk kích hoạt **theo tài liệu** (`doc_version`), có rollback; từng chunk chỉ duyệt (`review_status`) và tắt khẩn cấp (`is_active`) | B6 cần khái niệm "phiên bản đang kích hoạt" mỗi `doc_id` (hiện `is_active` theo dòng, hai bản có thể cùng bật) |
| Q4 | Làm B3 (usage thật từ trace + đơn giá theo model); trong lúc chờ hiển thị ước tính **có nhãn** | UI có trường nguồn số liệu (`thực tế` / `ước tính`) |
| Q5 | Giới hạn tin nhắn **4.000** ký tự theo backend, một hằng số dùng chung, có bộ đếm | Sửa F7 |
| Q6 | **Xoá code frontend cũ** (F9) cùng đợt thiết kế lại; giữ widget chat | Gỡ package chỉ code cũ dùng sau khi kiểm từng package |
| Q7 | Đăng nhập bằng **bảng tài khoản riêng** trong DB dịch vụ AI (tự băm mật khẩu, khôi phục, khoá tài khoản) | Thiết kế ở mục 14; chưa có code |
| Q8 | Có phân quyền theo vai trò; **đợt đầu chỉ làm vai trò `admin`** (toàn quyền) | Mô hình permission dựng sẵn để thêm kỹ thuật viên, reviewer sau, không đổi schema |
| Q9 | Băm mật khẩu bằng **`argon2-cffi`** (Argon2id) | Dependency mới đã được duyệt; thêm vào `backend/requirements.txt` cùng B1 |
| Q10 | Khôi phục mật khẩu đợt đầu **chỉ do admin đặt lại** (link một lần, hạn 30 phút, bắt đổi mật khẩu); email tự phục vụ để sau khi có SMTP | Không có màn "Quên mật khẩu" tự phục vụ ở đợt đầu |
| Q11 | Khoá **15 phút sau 5 lần sai liên tiếp**; phiên hết hạn sau **8 giờ không hoạt động**, tối đa **7 ngày** | Các giá trị đặt qua settings, mặc định như trên |
| Q12 | Màn tổng quan và danh sách hội thoại dành cả cho người không kỹ thuật: **không hiển thị token**; chỉ số là số hội thoại, chuyển nhân viên, **số câu hỏi**, **chi phí AI** (VND, nhãn ước tính). Token chỉ ở chi tiết lượt và trace | Backend phải trả số câu hỏi mỗi hội thoại và tổng số câu hỏi theo bộ lọc (B2) |
| Q14 | Bộ lọc "Trạng thái" ở Lịch sử hội thoại gồm **Hoàn tất, Chuyển nhân viên, Bị chặn, Lỗi**; "Chuyển nhân viên" **chỉ có ở kênh Website** (kênh CRM không handoff). **"Đã ngắt" không có trong bộ lọc**, chỉ hiện dạng nhãn khi xem "Tất cả" | Backend: `handoff` không phải giá trị `chat_history.status`; hiện `DisabledHandoffProvider` trả `None` nên `mode` luôn `bot` và `handoff_count` luôn 0. Dấu vết duy nhất: `conversation_state.last_intent` bắt đầu bằng `handoff.` (chỉ sub-query đầu tiên). Cần B2 thêm bộ lọc `handoff` theo dấu vết này hoặc cờ riêng; tới khi có handoff thật, nhãn nên là "Yêu cầu gặp nhân viên" |
| Q15 | Ô tìm kiếm Lịch sử hội thoại (gợi ý "Câu hỏi, mã ticket, model sản phẩm, mã hội thoại"): **câu hỏi của mọi lượt**; **mã ticket** (`TK-1048` và `#TK-1048`); **model sản phẩm** (`conversation_state.last_models`); **không dấu** ("bao loi" khớp "báo lỗi"); **mã hội thoại** (UUID, khớp chính xác). Có **bộ lọc riêng "Model sản phẩm"** (thay cho bộ lọc model AI, cập nhật 2026-11-17); model AI không nằm trong ô tìm hay bộ lọc của màn này. **Không** tìm trong câu trả lời của bot (ngoài MVP) | Hiện tại (`history_repository.py:192-194`) chỉ `ILIKE` trên `query_origin` và `model` của **lượt cuối**, phân biệt dấu, không escape `%`/`_`. Cần B2: truy vấn mới, `unaccent`, escape ký tự đại diện, index phục vụ tìm, tham số lọc model sản phẩm |
| Q16 | Bộ lọc "Model sản phẩm" có **7 mục** (Toma cập nhật 2026-11-17): **F54, F86, F10T, Astro 10S, Astro 6AH, Astro 6AV, Astro 10i** — giá trị gửi API là mã registry (`F54`, `F86`, `F10T`, `10S`, `6AH`, `6AV`, `10i`), nhãn hiển thị lấy tên trong registry (`registry.py:138-141`: "Astro 6AH"…). Registry còn `F86E, 6AHE, 6AVE, 10iV, 10iVE` (`registry.py:171-183`) không đưa vào bộ lọc | Không gõ cứng ở frontend: cần endpoint trả registry (mã, tên hiển thị) dùng chung cho bộ lọc này, support-chat và tài liệu (B8). Lọc theo `conversation_state.last_models` là các model được nhắc tới gần nhất, không phải mọi model trong hội thoại |
| Q17 | Màn duyệt tài liệu dùng **cách A**: PDF gốc nằm trên server CRM (link public), nhúng **trình xem PDF có sẵn của trình duyệt** (iframe, `…pdf#page=N`); **không** thêm `pdfjs-dist`, **không** tô vùng trên PDF. Chọn đoạn → mở đúng trang; đánh dấu đoạn đang chọn ở cột phải. Ảnh của đoạn vẫn lưu lên Supabase Storage | Đã kiểm link CRM (2026-11-17): `application/pdf`, `inline`, không chặn iframe; không có CORS cho Workspace, không hỗ trợ `Range` (trả đủ 8,3 MB). Nhảy trang có thể phải nạp lại iframe. **File CRM `F54 - Operation Guide.pdf` (8.332.391 byte) khác file doc-ingest đã xử lý (7.027.332 byte)** → phải xác nhận đúng phiên bản trước khi dùng `page_start`; cần bảng tài liệu lưu link CRM + hash + số trang (B6). Cách B (backend proxy có cache, kiểm hash, hỗ trợ `Range` + PDF.js ≥ 4.2.67 với `isEvalSupported: false` + `regions`) để sau |
| Q19 | Bộ lọc **Thời gian** ở Lịch sử hội thoại (đề xuất, mock 2026-11-17): Hôm nay / 7 ngày qua (mặc định) / 30 ngày qua / Tháng này / **Tuỳ chọn…**. Chọn Tuỳ chọn → mở bảng chọn khoảng ngay dưới bộ lọc: nút nhanh (Hôm nay, Hôm qua, Tuần này, Tháng này, Tháng trước), hai ô **Từ ngày / Đến ngày** (`input type=date` có sẵn của trình duyệt, không thêm dependency), Huỷ / Áp dụng. Kiểm tra: đủ hai ngày, từ ≤ đến, không quá hôm nay, tối đa 366 ngày — sai thì khoá Áp dụng và báo lỗi. Áp dụng → danh sách và các ô số liệu tải lại theo khoảng; hiện thẻ "Từ 01/11/2026 đến 17/11/2026 · 17 ngày" có "Sửa" và "×" (bỏ lọc về 7 ngày qua); ô chọn ghi "Tuỳ chọn: 01/11 – 17/11/2026" | Nghĩa của lọc: hội thoại có **ít nhất một lượt** trong khoảng (theo `chat_history.created_at`), không chỉ lượt cuối. Ngày tính theo **giờ Việt Nam** (UTC+7), cả hai đầu. API (B2): `from`, `to` dạng `YYYY-MM-DD` + múi giờ cố định `Asia/Ho_Chi_Minh`; backend đổi sang khoảng UTC `[from 00:00, to+1 00:00)`; endpoint chỉ số dùng cùng khoảng. Lưu khoảng đang lọc trên URL để chia sẻ được |
| Q18 | **Cho sửa trực tiếp `content` của đoạn trên web**, giữ bản cũ để rollback (Toma 2026-11-17, khác đề xuất ban đầu chỉ sửa phần AI). Mỗi lần sửa tạo **bản (revision) mới** của đoạn, lý do sửa **không bắt buộc** (đổi theo Q24); **khôi phục = tạo bản mới** có nội dung của bản cũ, không xoá lịch sử. Thẻ đoạn có nhãn "Đã sửa trên web · bản N", nút "Sửa nội dung", "Lịch sử (n bản)" với "Xem nội dung" (toàn văn bản đó, đánh số dòng, tô các dòng khác bản đang dùng, ghi "N dòng khác") và "Khôi phục bản này"; nhãn nội dung đổi từ "Nội dung gốc · trích từ PDF" thành "Nội dung · đã sửa trên web" | Hiện **không có** version cấp đoạn (version ở cấp tài liệu `doc_version`; đoạn chỉ có `content_hash`). Cần B6: bảng revision của đoạn (doc_id, doc_version, chunk_key, số bản, `content`, `content_hash`, nguồn `pdf`/`web`/`restore`, người sửa, thời điểm, lý do); sau khi lưu phải tạo lại `embed_text` + embedding của đoạn; `summary_vi`/`faq_vi`/`keywords` tạo từ bản cũ → báo "cần xem lại", nút "Tạo lại bằng AI" (tốn gọi LLM). Khi nạp phiên bản tài liệu mới: đoạn mới có `content_hash` = hash **bản PDF** của đoạn đã sửa → áp lại bản sửa, gắn nhãn; khác → báo "đã sửa ở bản trước, PDF mới đổi đoạn này" để người duyệt chọn. Rủi ro: nội dung chatbot trích dẫn khác chữ trên PDF mở theo `#page=N` (Q17); doc-ingest nạp lại phải không ghi đè bản sửa |
| Q20 | **Sửa nội dung một đoạn đã duyệt thì đoạn giữ trạng thái "Đã duyệt"**, không về Chờ duyệt (Toma 2026-11-17). Chatbot dùng nội dung mới ngay sau khi dựng lại dữ liệu tìm kiếm | Kết quả duyệt gắn với khóa đoạn, không với `content_hash` (mục 15 bước 3). Người sửa và lý do đã nằm trong revision (Q18); lưu thêm `revision_no` lúc duyệt để tab Đã duyệt / lịch sử cho thấy "đã sửa sau khi duyệt". Rủi ro chấp nhận: nội dung sửa vào chatbot mà không có người thứ hai xem |
| Q21 | **Thương hiệu** (Toma 2026-11-17): tên sản phẩm hiển thị **"QS AI Workspace"** (thay "Support Workspace"); logo QS Technology (chữ S + T, nâu và vàng) ở sidebar và màn đăng nhập. Bảng màu lấy từ logo: nâu `#482B09`, vàng `#E69D07`. Dùng: nút chính, link, viền chọn nâu `#5C3810` (hover `#482B09`); nền mục chọn `#F5EDE3`, viền chip chọn `#D9C3A5`; vàng chỉ làm điểm nhấn (vạch mục điều hướng đang chọn, link trên toast nền tối `#F5C25A`) | Màu trạng thái giữ nguyên (xanh lá hoàn tất/duyệt, đỏ lỗi, cam chờ duyệt/bị chặn, tím chuyển nhân viên) để không lẫn với thương hiệu. Không dùng vàng cho chữ trên nền trắng (tương phản < 3:1). Đã đo trên mock: chữ màu thương hiệu thấp nhất 9,6:1. File logo hiện có nền trắng; app thật cần bản nền trong suốt (SVG/PNG) cho nền tối và favicon. Tên trong tài liệu kỹ thuật vẫn gọi "Support Workspace" cho phần backend `/workspace` |
| Q22 | **Sidebar desktop** (Toma 2026-11-17, mock version 36): giống nhau ở mọi màn có sidebar. Gồm 5 mục (thêm Học tri thức "Thử nghiệm" ở mọi màn); khối tài khoản (ô "QT", tên, email · vai trò, **Đăng xuất**) ghim ở đáy. **Đứng yên khi cuộn** (`position: sticky; top: 0; height: 100vh`), chỉ nội dung bên phải cuộn; menu dài thì chỉ `<nav>` tự cuộn. **Thu gọn** bằng nút « / »: rộng 248px → 72px, chỉ còn icon; nhãn ẩn khỏi mắt nhưng trình đọc màn hình vẫn đọc, mỗi mục có tooltip; khối tài khoản còn ô "QT" + nút Đăng xuất dạng icon | App thật nhớ trạng thái thu gọn bằng `localStorage` (mock: state riêng từng màn, không nhớ khi chuyển màn). ≤ 720px: sidebar thành thanh trên, không sticky, ẩn nút thu gọn, menu cuộn ngang, còn ô "QT" + nút Đăng xuất dạng icon. Khác hướng dẫn `format.md` của canvas (khuyên không dùng sticky/`100vh` cho menu cạnh), chỉ áp dụng trên 720px theo yêu cầu. Màn Xem và duyệt (toàn khổ) và bản điện thoại không đổi |
| Q23 | **Chi tiết hội thoại ưu tiên thông tin nghiệp vụ** (Toma 2026-11-18, mock version 38). Mỗi lượt hiện: câu hỏi + "Khách hỏi · giờ", câu trả lời + "Chatbot trả lời · giờ", trạng thái kèm một câu giải thích cho lượt Lỗi / Bị chặn / Đã ngắt. Thời gian trả lời, token, chi phí, model AI, link diễn biến nằm trong "Chi tiết kỹ thuật" (thu gọn mặc định). Header bỏ LLM. Khung bên phải đổi thành "Tài liệu chatbot đã dùng · lượt N" (bấm "Tài liệu đã dùng (n)" ở từng lượt): ô Kết quả tra cứu / Số đoạn đã dùng / Độ khớp cao nhất; mỗi đoạn là một thẻ gồm thứ hạng, độ khớp (số + thanh), chủ đề (Lắp đặt / Vận hành / Cấu hình / Bảo trì), tài liệu nguồn + mục, nội dung 3 dòng + "Xem đầy đủ nội dung". Bỏ cột Trang. "Bảng tra cứu doc_chunks" và thời gian tra cứu chuyển vào "Chi tiết kỹ thuật của lần tra cứu". **Bố cục (version 42):** trang vừa khít chiều cao màn hình, không cuộn cả trang; hai khung "Các lượt hỏi đáp" và "Tài liệu chatbot đã dùng" đặt cạnh nhau, mỗi khung có tiêu đề cố định và tự cuộn bên trong; khung lượt mở ở cuối (lượt mới nhất), "Tải các lượt cũ hơn" ở đầu danh sách; chọn lượt khác thì khung tài liệu cuộn về đầu. ≤ 900px hai khung xếp chồng, mỗi khung cao tối đa 75% màn hình | Cột "Phạm vi" cũ **không phải intent**: là `scopes` của chính đoạn tài liệu (`doc_chunks.scopes`, giá trị trong `SCOPES` = installation/operation/configuration/maintenance, `extraction/registry.py:16`), đi qua `ChunkHit.scopes` (`retrieval/retriever.py:284`) vào snapshot (`chat_service.py:325`). Phân tích câu hỏi chỉ dùng scopes để **lọc** tra cứu. Backend cần bổ sung: (1) snapshot chưa lưu tài liệu nguồn — `ChunkHit` có `doc_id`, `section_title` nhưng `_retrieval_snapshot` và `ChunkResult` (`schemas/history.py:57`) không ghi → thêm hai trường; (2) `/chatbot/sessions/{id}/retrieval` chỉ trả lượt mới nhất có chunk → cần tham số `history_id` để xem theo từng lượt; (3) giờ hỏi/giờ trả lời dự kiến lấy `chat_history.created_at` / `updated_date` — cần kiểm lại cách ghi hai cột này khi làm backend. Điểm hiển thị là `score` (fused) như hiện có, chưa đổi thang |
| Q24 | **Sửa nội dung đoạn và lịch sử bản** (Toma 2026-11-18, mock version 39). (1) Ô "Lý do sửa" **không bắt buộc**; có thì ghi vào lịch sử, không có thì ghi "không ghi lý do". Chặn lưu chỉ khi nội dung rỗng hoặc không đổi. (2) Lịch sử dài: hiện 3 bản mới nhất + bản 1 (gốc từ PDF), các bản ở giữa gom vào nút "Xem thêm N bản cũ hơn" / "Thu gọn lịch sử"; nội dung từng bản vẫn thu gọn, bấm "Xem nội dung" mới mở. (3) Khung sửa ghi rõ "Nội dung mới · sửa từ bản N đang dùng, lưu sẽ thành bản N+1" (trước ghi "Nội dung (bản 3)" gây hiểu nhầm là đã có bản 3 đang chờ duyệt). Khung lịch sử có dòng giải thích: "Đang dùng" là bản nội dung hiện tại; trạng thái duyệt gắn với đoạn, không gắn với từng bản | `doc_chunk_revisions.reason` cho phép NULL. API lịch sử phân trang hoặc trả `revision_count` + 3 bản mới nhất + bản 1, lấy thêm khi mở rộng; không nạp toàn văn mọi bản ngay. Duyệt gắn với đoạn (Q20): sửa đoạn đã duyệt vẫn giữ "Đã duyệt"; đoạn "Chờ duyệt" vẫn chờ duyệt với nội dung của bản đang dùng |
| Q25 | **Mục lục và tìm kiếm ở màn duyệt tài liệu, kiểu Google Docs** (Toma 2026-11-18, mock version 40). Nút "Mục lục" mở khung trượt bên trái (điện thoại: sheet): cây dựng từ `section_path` (không đưa tên mục con sau "›" như "Note:", "Step 1:" lên cây), mỗi mục ghi "n đoạn · m chờ duyệt", thu/mở từng cấp, ô lọc tên mục. **Bấm mục = nhảy tới** đoạn đầu tiên của mục trong danh sách (không lọc); nút phễu "Chỉ hiện mục này" để lọc, có thẻ "Đang chỉ hiện mục … ×". Không có dòng vị trí (breadcrumb) phía trên ô tìm kiếm (Toma bỏ, version 41); mục đang xem chỉ được tô trong cây theo đoạn ở đầu vùng cuộn (scroll-spy). **Bố cục (version 44):** trang vừa khít chiều cao màn hình, không cuộn cả trang; cột PDF và cột đoạn kiến thức chiếm hết phần còn lại, mỗi cột tự cuộn; khung Mục lục cao bằng vùng hai cột, cây tự cuộn. ≤ 720px chỉ hiện một cột (nút chuyển "Đoạn kiến thức / PDF") và trang cuộn bình thường. Màn duyệt không hiện các dòng chú thích kỹ thuật (nguồn PDF, "Dữ liệu thật · doc_chunks_v2", hướng dẫn phím tắt — phím tắt chỉ còn ở tooltip ô tìm). Tìm kiếm: ô tìm trong cột đoạn, tô sáng trong nội dung, "i / n đoạn", nút lên/xuống (Enter / Shift+Enter, Esc xoá), "Chỉ hiện đoạn có kết quả"; mỗi đoạn khớp ghi "Khớp ở: nội dung / tiêu đề / tóm tắt tiếng Việt / câu hỏi tiếng Việt / từ khoá"; cây ghi số kết quả theo mục. So khớp không phân biệt hoa thường, dấu tiếng Việt, gạch nối | Dữ liệu `doc_chunks_v2` đáp ứng (kiểm 2026-11-18): `section_path` có ở mọi đoạn, `chunk_index` liên tục, 53 đoạn `parent` của F54 không đếm (243 đoạn lá), `review_status` theo đoạn, `fts` (từ `embed_text`, có GIN), `codes` (GIN). Tìm theo từ dùng `fts`; tìm một phần chữ (vd "M192") dùng `ILIKE` trên `content`/`section_title` (chưa cần `pg_trgm`, DB chưa cài); không dựa vào `fts_unaccent` (có thể bị bỏ). `summary_vi`/`faq_vi` chỉ F54 có → F86 và catalog chỉ tìm được bằng tiếng Anh hoặc mã. Cây phải khoá mục theo cả đường dẫn (F86 có hai mục "2.6"), gom đoạn không có `section_path` (F86: 1 đoạn) và đoạn mất cấp PART (F54: 47 đoạn lá, lỗi T-07) vào nhóm "Chưa xác định mục". Cần API: mục lục theo `doc_id` + `doc_version` (số đoạn theo trạng thái) và tham số `q`, `section`, `type`, `status` cho danh sách đoạn; tải đủ đoạn của một phiên bản (F54: 243) để nhảy tới không cần phân trang |
| Q26 | **Tải thêm và phạm vi tìm/lọc** (Toma 2026-11-18). (1) "Tải thêm" ở Lịch sử hội thoại tải **25 hội thoại** kế tiếp (cũ hơn) của kết quả đang lọc, nối vào cuối; "Tải các lượt cũ hơn" ở Chi tiết hội thoại tải **20 lượt** trước đó, chèn vào đầu khung, giữ nguyên vị trí đang đọc; mở chi tiết hiện 20 lượt gần nhất (hội thoại ≤ 20 lượt thì không có nút, hiện mốc "Đầu hội thoại"). Không tải hết một lần, không tự tải khi cuộn. (2) **Tìm kiếm và bộ lọc chạy trên toàn bộ dữ liệu ở server**, không chỉ phần đã tải: lọc → sắp xếp → chia trang; đổi bộ lọc thì tải lại từ đầu. (3) Ô số liệu và "Đang hiển thị x / y hội thoại khớp bộ lọc" tính trên toàn bộ kết quả lọc (y từ endpoint chỉ số cùng bộ lọc). (4) Đang tải: nút khoá + "Đang tải…"; hết dữ liệu (`next_cursor` rỗng): ẩn nút, hiện "Đã hiển thị hết"; lỗi: giữ dữ liệu đã có, báo lỗi + "Thử lại" | Phân trang con trỏ như mục "Phân trang" (B2): `/chatbot/conversations?limit=25&cursor=` theo `(last_message_at desc, session_id)`, `/history?limit=20&cursor=` theo `(created_at, id)`. Backend hiện tại (kiểm 2026-11-18, `history_repository.py` 187–236): chưa phân trang (trả hết); tìm kiếm chỉ khớp `query_origin` và `model` của **lượt mới nhất**; lọc trạng thái theo lượt mới nhất; chưa lọc kênh / thời gian / model sản phẩm; `aggregate_metrics()` tính toàn bảng, **bỏ qua bộ lọc** (F8). Màn duyệt tài liệu khác: tải đủ đoạn của một phiên bản nên tìm kiếm và số đếm trên cây luôn đầy đủ (Q25) |
| Q27 | **Màn "Khóa dịch vụ AI"** (Toma 2026-11-18, mock version 45; thay tên "Service keys"). Chữ trên giao diện: tiêu đề "Khóa dịch vụ AI", nút "Tạo khóa", "key" → "khóa", "integration" → "kênh tích hợp" (thẻ "Kênh CRM" / "Kênh Website", dòng phụ "Hệ thống dùng: CRM backend"), "Vô hiệu integration" → **"Tạm dừng kênh"** / "Mở lại kênh" (xác nhận gõ "Kênh CRM"), khóa của kênh tạm dừng ghi "Tạm ngừng theo kênh". Menu: sidebar "Khóa dịch vụ AI", thanh dưới điện thoại "Khóa AI". Form tạo khóa: **Kênh tích hợp** (Kênh CRM, Kênh Website; bỏ "+ Integration mới…"), **Tên khóa** 3–64 ký tự (bỏ ràng buộc chữ thường/gạch ngang), **trùng tên với khóa đã có trong cùng kênh thì tự thêm hậu tố -1, -2… tăng dần** và báo trước "khóa mới sẽ được lưu là …"; **Hết hạn**: 1 ngày / 7 ngày / 30 ngày (mặc định) / Không hết hạn, kèm dòng "Hết hạn ngày …". **Cửa sổ (version 46):** trang không mở sẵn khung nào; "Tạo khóa" mở cửa sổ nổi giữa màn hình (bấm nền hoặc Esc để đóng); tạo xong chuyển sang cửa sổ "Khóa mới" hiện khóa một lần — cửa sổ này không đóng khi bấm nền, Esc hoặc "Tôi đã lưu khóa" khi chưa sao chép thì cảnh báo; danh sách kênh dùng toàn bề rộng trang | Mã kỹ thuật vẫn giữ: bảng `service_integrations` / `service_keys`, định dạng `qsk_<key_id>_<secret>`, kênh `crm`/`website`. Hậu tố tên do **backend** tính trong cùng transaction khi tạo (tránh hai người tạo trùng cùng lúc), xét mọi khóa của kênh kể cả đã thu hồi/hết hạn; API trả tên cuối cùng. Tạm dừng kênh = cờ trên `service_integrations` (khóa không bị xoá). Tài liệu kỹ thuật và route vẫn gọi "service key" |
| Q13 | Trạng thái `cancelled` hiển thị **"Đã ngắt"** (không phải "Khách ngắt"): gồm cả khách website đóng trang và nhân viên CRM bấm dừng | Chỉ đúng khi CRM backend thật sự huỷ request `/chat/crm` lúc nhân viên bấm dừng; dịch vụ AI ghi `cancelled` khi kết nối bị đóng giữa lượt |

### Phân trang (yêu cầu của Q1–Q3)

Hiện không danh sách nào phân trang: `/chatbot/conversations` tính window function trên
**toàn bảng** `chat_history` rồi trả mọi session trong một response
(`history_repository.py` `list_conversations`); chunk chưa có API. Yêu cầu:

| Danh sách | Kiểu phân trang | Lý do |
|---|---|---|
| Hội thoại (`/chatbot/conversations`) | **Cursor (keyset)** theo `(last_message_at desc, session_id)`: `?limit=&cursor=` → `{items, next_cursor}` | Dữ liệu tăng liên tục; offset bị trượt khi có hội thoại mới chen lên đầu và chậm dần ở trang sâu |
| Lượt trong một hội thoại (`/history`) | Cursor theo `(created_at, id)`, tải thêm khi cuộn lên | Hội thoại CRM agent dài; hiện trả toàn bộ |
| Chunk của một phiên bản tài liệu | Offset/limit theo `chunk_index` (`?page=&page_size=`, có `total`) | Tập cố định, không đổi sau khi nạp; cần nhảy trang và hiện tổng |
| Phiên bản tài liệu, service key | Không cần (vài chục dòng); lọc phía server khi vượt ~100 | |

Bộ lọc và tìm kiếm chạy phía server, cùng tham số với phân trang. Chỉ số tổng
(`conversation_count`, chi phí…) tách thành endpoint riêng có cùng bộ lọc, để không phải
tính lại mỗi trang và khớp với danh sách đang xem (sửa F8). Cần index phục vụ thứ tự sắp
(đã có `chat_history_updated_date_idx`; thêm theo `session_id, created_at` cho `/history`).

## 14. Đăng nhập và phân quyền: thiết kế đã chốt (chưa có code)

Thiết kế đã được duyệt (Q7–Q11), chưa triển khai; không mô tả tính năng đã có. Prior art: `core/security/service_key.py`
(SHA-256 + `hmac.compare_digest`) chỉ hợp với secret ngẫu nhiên dài, **không** dùng cho mật
khẩu người dùng.

### 14.1 Dữ liệu (SQL áp tay, idempotent, theo DR-04)

| Bảng | Cột chính |
|---|---|
| `workspace_users` | `id`, `email` (unique, lowercase), `display_name`, `password_hash`, `role`, `status` (`active` \| `locked` \| `disabled`), `failed_login_count`, `locked_until`, `must_change_password`, `password_changed_at`, `last_login_at`, `created_at`, `created_by` |
| `workspace_sessions` | `id`, `user_id`, `token_hash` (SHA-256 của token ngẫu nhiên), `created_at`, `last_seen_at`, `expires_at`, `revoked_at`, `ip`, `user_agent` |
| `workspace_password_resets` | `id`, `user_id`, `token_hash`, `expires_at`, `used_at`, `created_by` |
| `workspace_audit_log` | `id`, `actor_user_id`, `action` (`login`, `login_failed`, `lock`, `unlock`, `password_reset`, `key_create`, `key_revoke`, `version_activate`…), `target`, `created_at`; chỉ metadata |

Vai trò → quyền ánh xạ trong code (`ROLE_PERMISSIONS`), route kiểm **permission** chứ không
kiểm tên role, để thêm vai trò mới không phải sửa route. Đợt đầu:
`admin = {conversations:read, chunks:read, chunks:review, versions:activate, service_keys:manage, users:manage}`.

### 14.2 Hành vi

| Vấn đề | Đề xuất |
|---|---|
| Băm mật khẩu | **`argon2-cffi`** (Argon2id; Toma duyệt dependency 2026-11-17, Q9). Hash dạng PHC chứa salt và tham số; dùng `check_needs_rehash` để nâng tham số khi đăng nhập thành công. Thêm vào `backend/requirements.txt` khi triển khai B1 |
| Phiên đăng nhập | Token ngẫu nhiên trong cookie `HttpOnly; Secure; SameSite=Strict`, DB chỉ lưu hash → thu hồi được ngay (đăng xuất, khoá, đổi mật khẩu). Không dùng JWT vì không thu hồi được trước hạn |
| Thời hạn | 8 giờ không hoạt động, tối đa 7 ngày (Q11; settings) |
| CSRF | Cookie `SameSite=Strict` + header `X-CSRF-Token` cho mọi POST/PATCH/DELETE (CORS đã cho phép header này) |
| Khoá tài khoản | Sai mật khẩu 5 lần liên tiếp → `locked_until = now + 15 phút` (Q11); admin mở khoá tay. Thông báo đăng nhập sai **giống nhau** cho mọi lý do (không lộ email có tồn tại) |
| Khôi phục mật khẩu | Đợt đầu (Q10): **admin đặt lại** → link/token dùng một lần, hạn 30 phút, bắt đổi mật khẩu khi đăng nhập. Gửi email tự phục vụ cần SMTP (hạ tầng chưa có, D-004) |
| Admin đầu tiên | CLI như `service_keys_cli`: `python -m app.modules.workspace.users_cli create-admin --email …`, in mật khẩu tạm một lần |
| Chính sách mật khẩu | Tối thiểu 12 ký tự, chặn trùng email; không ép ký tự đặc biệt |
| Kiến trúc | Router mới chỉ transport; `AuthService` (service) + `UserRepository`, `SessionRepository` (repository); dependency `require_permission("…")` cho mọi route Workspace, kể cả GET `/chatbot/*` hiện có (đóng DR-05) |

Cookie cần frontend và API cùng site: chạy Workspace sau cùng domain với dịch vụ AI qua
reverse proxy (như widget-backend), hoặc bật `CORS_ALLOW_CREDENTIALS=true` với origin cụ thể.

### 14.3 Màn hình frontend

| Màn | Nội dung | Trạng thái lỗi cần xử lý |
|---|---|---|
| Đăng nhập | Email, mật khẩu, nút đăng nhập | Sai thông tin (thông báo chung), tài khoản bị khoá (có thời điểm mở), bị vô hiệu |
| Đổi mật khẩu bắt buộc | Khi `must_change_password` | Mật khẩu yếu, trùng mật khẩu cũ |
| Đặt lại mật khẩu | Mở từ link admin cấp | Token hết hạn / đã dùng |
| Hồ sơ | Tên, đổi mật khẩu, đăng xuất, đăng xuất mọi phiên | |
| Quản lý tài khoản (admin) | Danh sách, tạo, đổi vai trò, khoá/mở khoá, vô hiệu, cấp link đặt lại | Không tự khoá/hạ quyền admin cuối cùng |
| Toàn app | Hết phiên (401) → về màn đăng nhập, giữ đường dẫn để quay lại; 403 → thông báo không đủ quyền; ẩn nút theo permission | |

### Trạng thái

Đã chốt toàn bộ (Q9–Q11). Thiết kế mục 14 đủ để triển khai B1.

## 15. Backend cho màn tài liệu khi `doc_chunks_v2` là bảng chính (kế hoạch, chưa có code)

Hiện trạng code liên quan: `DocChunkV2Repository` + `match_doc_chunks_v2` có nhưng **chỉ eval
dùng**; chat production nối `DocChunkRepository` (bảng cũ) ở `main.py`. `MatchV2Options`
mặc định `approved_only=True` → chuyển sang v2 lúc này **chat không tìm thấy gì** (356/356
draft). `load_ingest_run.py` xoá rồi insert lại cả `(doc_id, doc_version)` trong một
transaction. `chunk_key` = `{doc_id}:B{chunk_index}` (theo thứ tự, không ổn định giữa phiên
bản). Ranh giới import: code chat không import `doc_ingest` (test kiểm hai chiều).

### 15.1 Thay đổi dữ liệu (SQL idempotent, áp tay — DR-04)

| Bảng / cột | Mục đích |
|---|---|
| `documents` (`id` cố định vd `f54_operation`, `title`, `doc_type`, `domain`, `product_models`, `crm_document_id`) | Một tài liệu qua nhiều phiên bản; sửa đếm "Tổng số tài liệu" |
| `document_versions` (`document_id`, `doc_version`, `crm_file_url`, `file_sha256`, `page_count`, `source_run`, `status` `processing\|review\|active\|superseded\|failed`, `loaded_at`, `activated_at/by`; unique một `active` mỗi tài liệu) | Phiên bản đang dùng, rollback, link PDF (Q17), "Dùng từ" |
| `doc_chunks_v2.doc_id` → id cố định (migrate 356 dòng: `f54_operation_v02` → `f54_operation`…) | So phiên bản; giữ `chunk_key` cũ như mã mờ |
| `doc_chunk_reviews` (khóa đoạn, `content_hash`, `revision_no` lúc duyệt, `verdict` `ok\|fix`, `note`, `source` `manual\|carried\|sampled`, `reviewer`, `reviewed_at`) | Thay `chunk_review.json`; người/thời điểm cho tab Đã duyệt; `revision_no` để biết đoạn đã sửa sau khi duyệt (Q20) |
| `doc_chunk_revisions` (khóa đoạn, `revision_no`, `content`, `content_hash`, `source` `pdf\|web\|restore`, `base_revision`, `author`, `reason`, `created_at`) | Sửa/khôi phục/diff (Q18) |
| `match_doc_chunks_v2`: chỉ lấy đoạn của phiên bản `active` (join `document_versions` hoặc cờ đồng bộ lúc kích hoạt) | Chat chỉ dùng bản đang dùng |
| Supabase Storage: tải `assets` lên bucket `f54-docs`, `f86-docs` | Ảnh, phóng to (link có thời hạn) |

### 15.2 API (mọi route sau đăng nhập Workspace + permission — B1; phân trang Q3)

| Method + path (đề xuất, tiền tố `/workspace`) | Phục vụ |
|---|---|
| `GET /documents/summary` → `{total, live, pending, processing, pending_chunks}` | Ô thống kê |
| `GET /documents?zone=review\|live&search=&model=&cursor=` → thẻ: `id`, tên hiển thị (model + `doc_title`), nhãn `doc_type`, `models`, `version`, `kind` `new\|update`, `progress {approved, total, need_review}`, `next_action`, `status` | Hai vùng Cần duyệt / Đang sử dụng |
| `GET /documents/{id}/versions`; `POST /documents/{id}/versions/{v}/activate` (rollback = kích hoạt bản cũ) | Phiên bản |
| `GET /documents/{id}/versions/{v}/file` → `{crm_url, page_count, hash_matches}` | PDF cách A |
| `GET /documents/{id}/versions/{v}/chunks?status=&has_images=&section=&page=&page_size=` → đoạn theo `chunk_index` + nhóm mục cha, đủ trường của thẻ (M5), `assets[].signed_url`, `revision_no`, `review` | Cột phải màn duyệt |
| `POST …/chunks/{key}/review {verdict, note}`; `POST …/sections/{parent_key}/review` | Duyệt, Bỏ duyệt, Duyệt cả mục |
| `PATCH …/chunks/{key} {is_active, reason}` | Tắt khỏi chatbot |
| `GET …/chunks/{key}/revisions`, `GET …/revisions/{n}`, `GET …/revisions/{n}/diff?against=` | Lịch sử, xem bản, diff |
| `POST …/chunks/{key}/revisions {content, reason, base_revision}` (409 nếu `base_revision` cũ); `POST …/revisions/{n}/restore` | Sửa, khôi phục |
| `POST …/chunks/{key}/enrich` (job) | "Tạo lại bằng AI" |
| `POST /documents/sync` hoặc webhook CRM; `GET /ingest-jobs/{id}` | Đồng bộ CRM, trạng thái "Đang xử lý" |

CORS hiện chỉ `GET, POST, OPTIONS` → thêm `PATCH` (B10).

### 15.3 Luồng xử lý

1. **Chuyển chat sang v2**: nối `DocChunkV2Repository` sau cờ cấu hình (mặc định bảng cũ,
   rollback bằng cờ); chỉ bật khi đã có phiên bản `active` được duyệt. Cập nhật
   `retrieval_snapshot` mang `document_id`, `doc_version`, `chunk_key`, trang để màn "Kết quả
   chunk" mở thẳng đoạn trong Kho tài liệu.
2. **Đồng bộ CRM → phiên bản mới**: API phiên bản của CRM (chưa có contract) → so
   `doc_version`/hash với bản `active` → tạo `document_versions` `processing` → **worker nạp
   tài liệu riêng** (venv Docling, ngoài image chat) chạy doc-ingest `run` + `build` với carry từ
   bản `active` → báo cáo khác biệt (giữ nguyên / đổi / mới / bị bỏ theo `content_hash` +
   `section_path`) → làm giàu đoạn mới/đổi → embed → insert như bản mới → tải ảnh → `review`.
   Manifest (loại, model, scope) phải sinh từ dữ liệu CRM hoặc admin khai một lần mỗi tài liệu.
3. **Duyệt**: `review_status` tính từ `doc_chunk_reviews` theo **khóa đoạn** trong phiên bản
   (không còn tính lúc export từ file). Sửa trên web **không** xoá kết quả duyệt (Q20); khớp
   `content_hash` chỉ dùng khi mang kết quả duyệt sang phiên bản tài liệu mới (bản PDF). Quy tắc
   theo mức rủi ro cần duyệt riêng (đổi contract C2/D-009).
4. **Kích hoạt**: kiểm điều kiện → bản cũ `superseded`, bản mới `active` trong một transaction.
5. **Sửa trên web** (Q18, Q20): ghi revision → cập nhật `content`, `content_hash` → dựng lại
   `embed_text` + embedding; trạng thái duyệt giữ nguyên. Logic `embed_text` nằm trong `doc_ingest` (không import được từ
   chat) → chạy bằng worker hoặc tách builder dùng chung (cần quyết định).
6. **Loader**: không được xoá đoạn có revision `web` khi nạp lại cùng phiên bản; nạp phiên bản
   mới áp lại bản sửa khi hash PDF trùng, khác thì đánh dấu xung đột.

### 15.4 Thứ tự đề xuất

B1 đăng nhập → 15.1 schema + migrate `doc_id` → API đọc (summary, danh sách, phiên bản, đoạn,
file) cho hai màn chỉ xem → tải ảnh Storage → duyệt + bật/tắt + kích hoạt → chuyển chat sang
v2 → sửa/revision/diff → đồng bộ CRM + worker. Cần chốt: contract API phiên bản CRM; quy tắc
duyệt theo rủi ro; nơi dựng lại `embed_text` sau khi sửa.

## 16. Kiểm thử mock (2026-11-17, bản local `mock-preview/`)

Mock canvas nằm trong iframe khác domain, không kiểm trực tiếp được; đã chép 11 màn sang
`mock-preview/` (runtime tối giản `support.js`, chạy `npx vite mock-preview --port 5175`, cấu
hình `mock-preview` trong `.claude/launch.json`). Không phải code production. Đo bằng DOM ở
1440×900 và 375×812. Cột "Xử lý" ghi cách đã sửa trong mock (artifact version 32, cùng ngày);
mọi sửa đã kiểm lại bằng thao tác DOM trên `mock-preview/`.

| Màn | Kết quả lần đầu | Mức | Xử lý |
|---|---|---|---|
| Mọi màn | Render không lỗi runtime ở cả hai cỡ; 10/11 màn không tràn ngang | — | Sau sửa: 11/11 màn không tràn ngang ở 320, 375, 768, 1440px |
| Mọi màn có sidebar (375px) | Sidebar xếp lên đầu, cao 258–416px trước nội dung → cần thanh trên + menu thu gọn | Cao | Đã sửa: ≤720px sidebar thành thanh trên, menu một hàng cuộn ngang. Version 36 (Q22): thanh trên có nút Đăng xuất dạng icon; desktop thu gọn được và đứng yên khi cuộn |
| `.dc.html` | Không có `<meta name="viewport">` (canvas tự chèn) → app thật phải có, nếu không mobile vẽ ở 980px | Cao | Đã thêm vào cả 11 màn; app thật vẫn phải có trong `index.html` |
| Service keys (375px) | **Tràn ngang 63px**: hộp "Tạo service key" `flex-basis 340px` + lề 32px | Cao | Đã sửa: hộp co về 300px, `min-width: 0`, select rộng 100% |
| Lịch sử hội thoại (1440px) | Hàng bộ lọc 1 dòng ✓; dropdown ngày canh phải, nổi đè ✓; validation từ > đến ✓, khoá Áp dụng ✓; Áp dụng → thẻ lọc + nhãn ô chọn ✓ | — | — |
| Lịch sử hội thoại | Dropdown ngày **không đóng bằng Esc / bấm ra ngoài** | Trung bình | Đã sửa: Esc và bấm ra ngoài đều đóng (giữ khoảng đã áp dụng); focus vào ô "Từ ngày" khi mở |
| Lịch sử hội thoại | Ngày tương lai gõ tay chỉ báo "ngày bắt đầu phải trước…", **không có lỗi "không chọn ngày tương lai"** (`max` chỉ chặn bộ chọn) | Trung bình | Đã sửa: kiểm ngày tương lai trước, báo "Không chọn ngày sau hôm nay (17/11/2026)." |
| Lịch sử hội thoại | Lọc ra 0 kết quả: bảng trống, vẫn "Đang hiển thị 0 hội thoại" + nút **Tải thêm**; **không có trạng thái rỗng** | Cao | Đã sửa: khối rỗng "Không có hội thoại khớp bộ lọc" + "Xoá bộ lọc"; ẩn bảng và Tải thêm. Ô tìm kiếm và Model sản phẩm giờ lọc thật trên dữ liệu mẫu |
| Lịch sử hội thoại | Ô số liệu vẫn ghi "trong 7 ngày qua" sau khi chọn khoảng tuỳ chọn | Thấp | Đã sửa: cả 4 ô ghi theo khoảng đang chọn |
| Lịch sử hội thoại (375px) | Dropdown ngày **bị cắt 17px bên trái** (canh phải theo ô hẹp) → trên mobile cần canh hai mép ô / toàn màn | Trung bình | Đã sửa: ≤720px dropdown canh theo cả khối bộ lọc |
| Xem và duyệt | Chọn đoạn → nhãn trang PDF cập nhật ✓; "Xem thêm 3 hình" 2 → 5 ✓, "Thu gọn hình" ✓; nút ‹ › phóng to quay vòng 1/5 ↔ 5/5 ✓ | — | — |
| Xem và duyệt | Tab "Đã duyệt" **trống trơn**; bộ đếm luôn "8 / 243 đoạn" ở mọi tab (tab Có hình chỉ có 6) | Cao | Đã sửa: tab lọc theo trạng thái thật; bộ đếm theo tab; tab rỗng có câu giải thích + "Xem tất cả đoạn" |
| Xem và duyệt | Phóng to: **Esc, ← → không hoạt động**, focus không vào lớp phủ | Trung bình | Đã sửa: Esc đóng, ← → chuyển hình (quay vòng), focus vào nút Đóng. Chưa giữ focus trong lớp phủ và trả focus khi đóng |
| Xem và duyệt | "Lưu bản mới" khi **chưa nhập lý do**: đóng form, **mất chỗ đã sửa**, không báo lỗi | Cao | Đã sửa: giữ form, báo lỗi dưới form (rỗng / chưa đổi / thiếu lý do); lưu hợp lệ tạo bản N+1 + toast. Huỷ khi có thay đổi → hỏi "Bỏ nội dung đang sửa?" |
| Xem và duyệt | "Khôi phục bản này", "Duyệt", "Tắt khỏi chatbot", "Duyệt cả mục", "Tạo lại bằng AI": **không phản hồi** | Cao | Đã sửa: Duyệt → nhãn "Đã duyệt" + toast Hoàn tác; Duyệt cả mục → hộp xác nhận nêu số đoạn; Tắt → hộp xác nhận bắt buộc lý do; Khôi phục → hộp xác nhận nêu số dòng khác, tạo bản mới; Tạo lại bằng AI → toast minh hoạ. Thêm "Bỏ duyệt" và "Bật lại" làm thao tác ngược (cần chốt, xem dưới) |
| Xem và duyệt (375px) | Khung PDF cao ~1.130px nằm trên danh sách đoạn → mobile cần chuyển tab "PDF / Đoạn" | Trung bình | Đã sửa: ≤720px có nút chuyển "Đoạn kiến thức / PDF"; "Mở trang này trong PDF" trong lớp phóng to tự chuyển sang PDF |
| Service keys | Toàn màn tĩnh | — | Đã thêm: tạo key (kiểm tên, trùng tên), hiện key một lần, cảnh báo khi bấm "Tôi đã lưu key" mà chưa sao chép, thu hồi key và vô hiệu integration phải gõ đúng tên |

Chưa làm trong mock, để lúc làm app thật: toast lỗi và banner trang (401/403/DB lỗi), khung
xương lúc tải, giữ focus trong lớp phủ, chặn chuyển trang khi đang sửa, lọc thời gian trên dữ
liệu mẫu (chỉ đổi nhãn), màn Tài khoản vẫn tĩnh.

Cần chốt: "Bỏ duyệt" (đoạn đã duyệt về Chờ duyệt) và "Bật lại" (đoạn đã tắt về Chờ duyệt) là
thao tác tôi thêm vào mock cho đủ vòng; chưa có trong thiết kế backend mục 15. Đã chốt (Q20):
lưu bản mới cho một đoạn đã duyệt giữ trạng thái "Đã duyệt", đúng như mock đang làm.

### Bộ thông báo cần thiết kế (áp dụng mọi màn)

| Loại | Dùng cho | Hành vi |
|---|---|---|
| Toast thành công | Duyệt, bỏ duyệt, tắt đoạn, lưu bản mới, kích hoạt, sao chép key/link | Tự ẩn 4–6 s; "Hoàn tác" cho thao tác đảo ngược được |
| Toast lỗi | Lỗi mạng/server | Không tự ẩn; `request_id`; "Thử lại" |
| Hộp xác nhận | Thu hồi key, vô hiệu integration, khoá/vô hiệu tài khoản, kích hoạt phiên bản, khôi phục bản (kèm diff), duyệt cả mục | Nêu hậu quả; thao tác không hoàn tác được thì gõ lại tên |
| Lỗi trong form | Đăng nhập, lý do sửa, tên key, email, khoảng ngày | Dưới ô, khoá nút gửi, focus vào ô lỗi |
| Banner trang | Hết phiên (401), không đủ quyền (403), DB lỗi, tắt lưu trace, chưa có tài liệu đang dùng | Đầu khu nội dung, không tự ẩn |
| Trạng thái rỗng / đang tải | Danh sách, ô số liệu, chunk, trace (404 `trace_not_found` là thường gặp) | Khung xương khi tải; câu giải thích + hành động khi rỗng |
| Chặn rời trang | Đang sửa nội dung đoạn chưa lưu | Hỏi trước khi Huỷ / chuyển trang |
| Bàn phím | Dropdown, lớp phóng to, hộp xác nhận | Esc đóng, ← → chuyển hình, giữ focus trong lớp phủ, trả focus khi đóng. Bắt phím trên chính lớp phủ, không nghe toàn trang (mock version 33 đã đổi theo cách này) |

## 17. Bản điện thoại (mock 2026-11-17, version 33)

Toma chốt mock desktop hiện tại làm giao diện version 1, rồi yêu cầu thêm bản cho người dùng
điện thoại. Hàng "Bản điện thoại · 390×844" trên canvas có 8 màn tương tác (M1–M7). Mọi màn
dùng chung quyết định Q1–Q20 với desktop; chỉ đổi cách trình bày.

### Mẫu chung

| Thành phần | Bản điện thoại | Lý do |
|---|---|---|
| Điều hướng | Thanh dưới 4 mục: Hội thoại, Tài liệu, Service keys, Tài khoản. Màn chi tiết (hội thoại, diễn biến, duyệt tài liệu) ẩn thanh dưới, có nút quay lại trên thanh trên | Ngón cái với tới; màn chi tiết cần chỗ |
| Thanh trên | Cao 56px: tiêu đề + tối đa một nút (chat thử, tạo key, thêm tài khoản) | — |
| Bộ lọc, form, xác nhận | Sheet trượt từ dưới lên. Bấm nền tối hoặc nút × để đóng; Esc khi có bàn phím | Thay dropdown và hộp thoại giữa màn |
| Bảng | Thành thẻ (hội thoại, key, tài khoản, đoạn tài liệu); các bước diễn biến thành danh sách dọc, mỗi bước có thanh thời gian nhỏ | Bảng nhiều cột không đọc được ở 390px |
| Vùng bấm | Tối thiểu 44px; ô nhập cỡ chữ 16px (iOS không tự phóng to) | — |
| Thông báo | Một toast trên thanh dưới, tự ẩn 6 giây, có "Hoàn tác" khi đảo ngược được | — |

### Từng màn

| Màn | Khác bản desktop |
|---|---|
| M1 Đăng nhập | Nút Hiện/Ẩn mật khẩu; lỗi chung "Email hoặc mật khẩu không đúng" (không lộ lý do). Version 47 (áp dụng cả desktop): bỏ dòng "Quên mật khẩu…" và khối "Trạng thái khác" (tạm khoá, hết phiên — vẫn là thông báo của app thật khi xảy ra, chỉ không vẽ sẵn); desktop có Hiện/Ẩn mật khẩu; đăng nhập đúng chuyển thẳng tới Lịch sử hội thoại (app thật: hoặc trang đang xem trước khi hết phiên) |
| M2 Lịch sử hội thoại | Ô tìm kiếm + hàng chip: "Bộ lọc · n", khoảng thời gian, từng bộ lọc đang bật (bấm × để bỏ). Sheet bộ lọc chỉnh bản nháp; nút "Xem N hội thoại" mới áp dụng; Tuỳ chọn ngày kiểm tra như Q19. Số liệu lưới 2×2. Danh sách dạng thẻ |
| M3 Chi tiết hội thoại | Lượt dạng bong bóng; "Đoạn tài liệu đã dùng (n)" mở sheet kết quả tra cứu; lượt lỗi có "Xem diễn biến xử lý" |
| M4 Diễn biến (lỗi) | Banner lỗi, tóm tắt 2×2, các bước dọc bấm để mở chi tiết, nút "Chỉ bước lỗi". Chỉ vẽ lượt Lỗi; lượt khác dùng cùng bố cục |
| M5a Kho tài liệu | Ba ô số liệu, thẻ tài liệu cần duyệt, vùng đang dùng |
| M5b Xem và duyệt | Thanh tiến độ duyệt; chuyển "Đoạn kiến thức / PDF"; chip lọc có số đếm; thẻ đoạn rút gọn (ảnh 3 ô, ô thứ ba ghi "+n"); phần AI thu gọn. Sửa nội dung mở sheet toàn màn; lịch sử và khôi phục trong sheet; xem ảnh toàn màn. Tab PDF: nút "Mở PDF ở trang N" mở trình xem của máy (tab mới) + bản xem nhanh |
| M6 Service keys | Mỗi key một thẻ; tạo key và hiện key một lần trong sheet; thu hồi và vô hiệu integration gõ đúng tên |
| M7 Tài khoản | Thẻ tài khoản đang đăng nhập + Đăng xuất; không tự khoá chính mình; khoá có xác nhận; link đặt lại trong sheet |

Chưa có trên điện thoại: Học tri thức (thử nghiệm), màn diễn biến cho lượt hoàn tất / bị chặn
/ đã ngắt (theo bố cục M4). Các việc chưa làm của mục 16 (toast lỗi, banner trang, khung xương,
giữ focus) áp dụng cả bản điện thoại.

Kiểm thử trên `mock-preview/` (khung 390×844): không tràn ngang ở cả 8 màn, không lỗi runtime.
Các luồng đã chạy: lọc (kể cả lỗi ngày tương lai và bỏ chip), tạo / sao chép / thu hồi key,
duyệt + hoàn tác, duyệt cả mục, sửa (lỗi + bỏ thay đổi + lưu), khôi phục, tắt (bắt buộc lý do,
Esc), xem ảnh ← →, khoá tài khoản, link đặt lại, đăng nhập. Lỗi tìm ra và đã sửa: thẻ có
`overflow: hidden` trong thân trang bị co và cắt nội dung (thêm `flex-shrink: 0`).

## 18. Kế hoạch triển khai frontend v1 (2026-11-18, GĐ 0 xong, GĐ 1 xong phần giao diện)

Giao diện chuẩn: canvas "QS AI Workspace mock" **version 47** (desktop 1–7, điện thoại M1–M7)
cùng quyết định Q1–Q27. Mock là bản vẽ, không phải code để chép: dựng lại bằng React theo
cấu trúc dưới đây. Trạng thái thực hiện theo dõi ở
[flows/workspace-ui/STATE.md](flows/workspace-ui/STATE.md).

### 18.1 Hiện trạng làm nền (kiểm 2026-11-18)

| Hạng mục | Hiện có | Ảnh hưởng tới kế hoạch |
|---|---|---|
| Khung app | React 18 + Vite 7, JavaScript/JSX, CSS Modules; `App.jsx` chỉ có route `/` → `pages/SupportWorkspace.jsx` (bản Workspace cũ, gọi thẳng `/chatbot/*`) | Dựng Workspace mới trong `src/workspace/`, thay route `/`; bản cũ giữ tới khi bản mới chạy đủ rồi xoá |
| Thư viện sẵn có | `react-router-dom` 7, `axios` (`services/api.service.js`, `withCredentials`), `lucide-react` (icon), `i18next`, `dompurify`, `react-markdown` | **Đủ để dựng v1, không cần dependency mới** (TR-08). Icon dùng `lucide-react` thay SVG vẽ tay của mock |
| Widget chat | `components/ChatbotWidget.jsx` + `chatbot/Chatbot.jsx`, gọi widget-backend qua `/api` (cookie HttpOnly) | Giữ nguyên làm khung chat thử (nút nổi), không đổi luồng widget |
| Trang cũ không dùng | `pages/Blogs`, `NewBlog`, `Services`, `Contact`… không có route | Không đụng (TR-09); dọn trong việc riêng nếu Toma muốn |
| Kiểm thử frontend | Chỉ `npm run lint` + `npm run build`; **chưa có test runner** | Thêm Vitest + Testing Library là dependency mới → cần Toma duyệt (18.6) |
| API dịch vụ AI | Có: `GET /chatbot/conversations`, `/sessions/{id}/history`, `/retrieval`, `/trace` (chưa xác thực, DR-05) | Màn hội thoại dựng được ngay ở mức đọc; phần còn lại chờ B1, B2, B5, B6, B7 |

### 18.2 Kiến trúc frontend

- **Thư mục** `src/workspace/` (bố cục thực tế sau GĐ 0, xem README của luồng):
  - `WorkspaceApp.jsx` (router), `layout/` (khung, menu), `auth/` (provider, guard, quyền);
  - `components/`, `hooks/`, `pages/` (dùng chung);
  - `features/<màn>/` (trang + hook của màn, từ GĐ 1);
  - `api/` (client, lỗi, CSRF, mỗi tài nguyên một file, `fixtures/`);
  - `styles/tokens.css`, `strings.vi.js`, `config.js`.
- **Định tuyến** (`react-router-dom` 7). Mỗi màn có URL riêng, bộ lọc nằm trên query string để chia sẻ được (Q26):

  | Đường dẫn | Màn |
  |---|---|
  | `/login` · `/reset-password?token=` · `/change-password` | Đăng nhập, đặt lại, đổi mật khẩu bắt buộc (14.3) |
  | `/conversations?channel=&status=&model=&time=&from=&to=&q=` | Lịch sử hội thoại |
  | `/conversations/:sessionId` · `…/turns/:historyId/trace` | Chi tiết hội thoại · Diễn biến xử lý |
  | `/documents` · `/documents/:docId/versions/:version` | Kho tài liệu · Xem và duyệt |
  | `/keys` | Khóa dịch vụ AI |
  | `/users` | Tài khoản |
- **Khung trang dùng chung:**
  - Sidebar Q22: đứng yên, thu gọn còn icon, nhớ trạng thái bằng `localStorage`, khối tài khoản ghim đáy.
  - Từ 720px trở xuống chuyển thành thanh dưới 4 mục (Q-mobile, mục 17).
  - **Một bộ component đáp ứng mọi cỡ màn**, không làm app điện thoại riêng: các màn M1–M7 của mock là cách hiển thị ở cỡ hẹp.
- **Lớp API** (`api/client.js`, dùng `fetch` của trình duyệt):
  - Không dựa trên `apiFetch`/`axios` sẵn có: `npm audit` báo nhiều cảnh báo cho `axios` ^1.11 (2026-11-18), và `fetch` đủ dùng nên không cần gói mới.
  - `credentials: 'include'`; tự gắn `X-CSRF-Token` (đọc từ cookie `ws_csrf`, tên giả định tới khi làm B1) cho POST/PUT/PATCH/DELETE.
  - 401 → về `/login?next=<đường dẫn>`; 403 → banner "không đủ quyền".
  - Lỗi mạng hoặc 5xx → báo lỗi kèm "Thử lại", giữ `request_id`.
  - Mỗi tài nguyên một file (`conversations.js`, `documents.js`, `keys.js`, `users.js`, `auth.js`). Màn hình không gọi `fetch`/`axios` trực tiếp.
- **Dữ liệu và trạng thái:**
  - Không thêm React Query. Dùng một số hook nhỏ tự viết:
    - `useResource` (tải, huỷ bằng `AbortController`, thử lại);
    - `useCursorList` (Tải thêm theo `next_cursor`, đổi bộ lọc thì tải lại từ đầu, Q26);
    - `useUrlFilters`.
  - Người dùng hiện tại và quyền lấy từ `GET /workspace/auth/me` (đường dẫn giả định, chốt ở B1), đặt trong context `AuthProvider`. Nút bị ẩn hoặc khoá theo permission (14.1), không theo tên vai trò.
- **Giao diện:**
  - `tokens.css` giữ biến màu Q21 (nâu `#5C3810` / `#482B09`, vàng `#E69D07`, nền chọn `#F5EDE3`, màu trạng thái), cỡ chữ, bo góc, khoảng cách.
  - Font Inter qua thẻ `<link>` trong `index.html`.
  - CSS Modules cho từng component.
- **Ngôn ngữ:** v1 chỉ tiếng Việt, chuỗi gom vào `src/workspace/strings.vi.js` (chưa nối i18next) để sau dịch không phải đi lục từng file.
- **Kết nối và cookie:**
  - Dev: Vite proxy `/workspace`, `/chatbot` → `:8000`, giống cấu hình đã dùng ở `.claude/vite.worktree.config.js`.
  - Production: frontend và dịch vụ AI chạy cùng domain qua reverse proxy (14.2). Nếu không cùng domain thì phải bật `CORS_ALLOW_CREDENTIALS`. Việc này thuộc deploy, cần ghi vào `rules/deploy-rules.md`.

### 18.3 Bộ component dùng chung

Năm dòng đầu dựng xong ở GĐ 0 (`Field` tách thành `TextField`, `SelectField`; `Sheet` là
`Modal` tự chuyển thành sheet đáy ở ≤ 720px). Ba dòng cuối gắn với một màn nên dựng trong
giai đoạn của màn đó.

| Component | Dùng ở | Hành vi bắt buộc (từ mock và mục 16) |
|---|---|---|
| `AppShell`, `Sidebar`, `TabBar` | Mọi màn | Q22; ≤ 720px thanh dưới; trang vừa khít màn hình ở các màn 2 khung |
| `Button`, `IconButton`, `Badge`, `Card`, `Field` (input/select/textarea + lỗi) | Mọi nơi | Vùng bấm ≥ 44px trên điện thoại; ô nhập 16px; focus thấy rõ |
| `Modal`, `Sheet` (điện thoại), `ConfirmDialog` (có tuỳ chọn gõ lại tên, tuỳ chọn lý do) | Khóa, tài khoản, duyệt | Bắt phím ngay trên lớp phủ (Esc), không nghe phím toàn trang; giữ focus trong lớp phủ, trả focus khi đóng (mục 16 còn thiếu) |
| `Toast` (có Hoàn tác, tự ẩn 6 giây) và `ErrorBanner` | Mọi nơi | Toast lỗi không tự ẩn, có "Thử lại" (mục 16) |
| `EmptyState`, `Skeleton`, `LoadMore` | Danh sách | "Đang hiển thị x / y", đang tải, đã hết, lỗi (Q26) |
| `FilterBar`, `DateRangeDropdown`, `FilterSheet` | Lịch sử hội thoại | Q19; bản nháp trong sheet, Áp dụng mới lọc |
| `OutlineTree`, `SearchHighlight` | Duyệt tài liệu | Q25: nhảy tới, lọc mục, theo dõi mục khi cuộn, tô sáng, lên/xuống |
| `ImageViewer` | Duyệt tài liệu | ← → Esc; điện thoại vuốt và chụm |

### 18.4 Giai đoạn và phụ thuộc backend

Thứ tự theo giá trị và độ sẵn sàng của backend. Màn nào thiếu API thì dựng giao diện theo
contract đã chốt và chạy với **dữ liệu giả** (`VITE_WORKSPACE_FIXTURES=1`, chỉ trong dev,
mặc định tắt). Không mô tả màn chạy fixture là đã xong (TR-10).

| GĐ | Nội dung | Backend cần | Sẵn sàng hôm nay | Xong khi |
|---|---|---|---|---|
| 0 | Nền: thư mục, router, `AppShell`/sidebar/thanh dưới, tokens, component 18.3, lớp API, fixture, trang lỗi 404/403 | — | Có | **Xong 2026-11-18.** 27 test đạt, build đạt, code mới 0 lỗi lint (toàn repo còn 141 lỗi có sẵn ở trang cũ); `/` → Workspace mới, bản cũ ở `/legacy` |
| 1 | Đăng nhập, đặt lại, đổi mật khẩu bắt buộc, `AuthProvider`, chặn route, 401/403, đăng xuất | **B1** (bảng tài khoản, phiên cookie, CSRF, `/workspace/auth/*`; contract giả định ở README luồng workspace-ui) | Không. Dựng với fixture | **Giao diện xong 2026-11-18** (fixture). Còn: đăng nhập thật được trên dev; mọi route Workspace yêu cầu đăng nhập (đóng DR-05) |
| 2 | Lịch sử hội thoại, Chi tiết (2 khung tự cuộn), Diễn biến xử lý (4 trạng thái) | Đọc: **có sẵn**. Bổ sung: **B2** (phân trang, lọc kênh/thời gian/model, chỉ số cùng bộ lọc), **B5** (`/retrieval?history_id`, tài liệu nguồn), **B4** (chi phí) | Một phần: danh sách, lịch sử, trace đọc được ngay; bộ lọc chạy trên server chỉ có `search`, `status` | Đủ Q12–Q16, Q19, Q23, Q26 khi B2/B5 xong; trước đó ẩn các bộ lọc chưa có API thay vì lọc ở trình duyệt |
| 3 | Khóa dịch vụ AI | **B7** (API tạo/thu hồi khóa, tạm dừng kênh, tự thêm hậu tố tên, `last_used_at`) | Không (hiện chỉ có CLI) | Đủ Q27 |
| 4 | Tài khoản (danh sách, tạo, khoá/mở, vô hiệu, cấp link đặt lại) | **B1** | Không | Đủ 14.3; không tự khoá chính mình hay admin cuối cùng |
| 5 | Kho tài liệu, Xem và duyệt (PDF, Mục lục, tìm kiếm, sửa/lịch sử/khôi phục, duyệt/tắt, ảnh) | **B6** (mục 15), ảnh trên Storage, sửa T-07 để cây mục đúng | Không | Đủ Q17, Q18, Q20, Q24, Q25 trên dữ liệu thật `doc_chunks_v2` |
| 6 | Hoàn thiện: rà khả năng truy cập, cỡ điện thoại, hiệu năng danh sách, xoá `SupportWorkspace.jsx` cũ | — | — | Danh sách kiểm 18.5 đạt ở mọi màn |

Học tri thức (thử nghiệm) chỉ hiện khi endpoint capability báo bật (B8, cờ
`LEARNING_API_ENABLED`); v1 không dựng lại màn này.

Đề xuất làm song song: frontend GĐ 0 → 2 (phần đọc) trong lúc backend làm B1 → B2 → B7 → B6;
mỗi màn nối API thật ngay khi endpoint tương ứng xong.

### 18.5 Tiêu chí xong cho mỗi màn

1. Khớp mock version 47 ở desktop (1280–1440px) và điện thoại (375–390px); không tràn ngang ở 320, 375, 768, 1024, 1440px.
2. Đủ trạng thái: đang tải (khung xương), rỗng (câu giải thích + hành động), lỗi (thử lại), 401, 403, hết dữ liệu.
3. Bàn phím và trình đọc màn hình: nhãn cho mọi ô nhập, `aria-*` cho nút chỉ có icon, Esc ở lớp phủ, focus không bị lạc.
4. Không lộ chữ kỹ thuật ra người dùng không chuyên kỹ thuật (Q23, Q27): thông số kỹ thuật nằm trong phần "Chi tiết kỹ thuật".
5. `npm test`, `npm run build` đạt; code của màn không có lỗi lint. Có test cho hook và component chính.
6. Chạy được với backend thật trên dev cho phần API đã có; phần còn dùng fixture ghi rõ trong `STATE`/`LOG`.

### 18.6 Đã chốt trước khi bắt đầu (Toma duyệt cả 5 đề xuất, 2026-11-18)

| Việc | Đề xuất | Lý do |
|---|---|---|
| Thêm Vitest + `@testing-library/react` + `jsdom` (devDependencies) | Đồng ý | Hiện không có test frontend; hook phân trang, bộ lọc URL, phân quyền cần test tự động |
| Workspace mới chiếm route `/`, bản cũ dời sang `/legacy` rồi xoá ở GĐ 6 | Đồng ý | Một app duy nhất, tránh 2 bản song song lâu |
| Dữ liệu giả cho màn chưa có API (`VITE_WORKSPACE_FIXTURES`, chỉ dev) | Đồng ý | Làm frontend song song backend mà không phải đợi |
| v1 chỉ tiếng Việt, chuỗi gom một file | Đồng ý | Người dùng nội bộ; i18n để sau |
| Mở luồng tài liệu frontend riêng trong `docs/ai/flows/workspace-ui/` (README/STATE/LOG) và thêm vào chỉ mục `AGENTS.md` | Đồng ý | Theo quy trình tài liệu theo luồng; mục này giữ vai trò yêu cầu |

### 18.7 Rủi ro

| Rủi ro | Cách giảm |
|---|---|
| Cookie phiên không gửi được khi frontend và API khác domain | Chốt reverse proxy cùng domain trước GĐ 1; dev dùng Vite proxy |
| API GET `/chatbot/*` đang công khai (DR-05) trong lúc chưa có B1 | Không deploy Workspace mới ra ngoài trước khi B1 xong |
| Cây mục sai do lỗi T-07 (60 đoạn F54) và 2 lỗi F86 | Sửa T-07 trước GĐ 5; cây có nhóm "Chưa xác định mục" |
| Danh sách hội thoại trả hết một lần (chưa phân trang) | Ưu tiên B2 trước khi dữ liệu lớn; tạm giới hạn hiển thị phía client |
| Ảnh đoạn tài liệu chưa có trên Storage | GĐ 5 phụ thuộc việc tải ảnh lên; trước đó hiện khung thay thế |