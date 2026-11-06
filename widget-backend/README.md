# widget-backend

Backend cho chatbot widget (`src/chatbot`). Đây là "backend website" trong mô hình
tích hợp: trình duyệt chỉ nói chuyện với server này, server này gọi dịch vụ AI
(`backend/`) bằng service key.

```
Trình duyệt ──cookie HttpOnly qs_visitor, qs_chat_session──▶ widget-backend
widget-backend ──Authorization: Bearer qsk_… + {session_id, message}──▶ dịch vụ AI POST /chat/website
```

- `CHATBOT_API_KEY` chỉ nằm ở server này, không bao giờ xuống trình duyệt.
- `qs_visitor` định danh khách ẩn danh (log, rate limit sau này); **không** gửi sang
  dịch vụ AI.
- `qs_chat_session` giữ `session_id` do dịch vụ AI cấp (đọc từ header
  `X-Session-ID`). Trình duyệt không thấy giá trị này; session gắn với khách vì
  cookie nằm trong trình duyệt của chính khách.

Node.js ≥ 22, không có dependency.

## Chạy

```powershell
# 1. Cấp key kênh website (trong backend/, sau khi áp backend/sql/service_keys.sql)
.\venv\Scripts\python.exe -m app.modules.chatbot.service_keys_cli create --integration-id website_main --channel website

# 2. Cấu hình và chạy
cd widget-backend
copy .env.example .env    # điền CHATBOT_API_KEY
npm start                 # :8787
npm test
```

Khi phát triển, `npm run dev` ở repo root (Vite) proxy `/api` sang `:8787`, nên
widget và server này cùng origin. Production cần đặt server này sau cùng domain
với trang web (reverse proxy `/api`) và bật `COOKIE_SECURE=true`.

## API cho widget

| Route | Mô tả |
|---|---|
| `POST /api/chat` `{message: {text}, client_context?}` | Trả `text/event-stream` của dịch vụ AI. Session hết hạn → tự mở hội thoại mới một lần |
| `GET /api/chat/history` | `{messages: [...]}` của hội thoại hiện tại; chưa có thì rỗng |
| `POST /api/chat/crm` `{user_id, crm_access_token?, message: {text}}` | **Chỉ để kiểm thử** kênh CRM (xem dưới) |
| `POST /api/chat/reset` | Xoá cookie session website và CRM (cuộc trò chuyện mới), 204 |
| `GET /health` | `{status: "ok"}` |

Lỗi có dạng `{"detail": {"code", "message", "request_id"}}`:

| HTTP | `code` | Khi nào |
|---|---|---|
| 400 | `invalid_json` / `invalid_request` | Body sai |
| 403 | `origin_not_allowed` | POST từ origin ngoài `ALLOWED_ORIGINS` |
| 413 | `payload_too_large` | Body > 16 KB |
| 502 | `chat_unavailable` | Dịch vụ AI từ chối key (401/403) hoặc lỗi 5xx khác 503; chi tiết chỉ ở log server |
| 502 | `ai_service_unreachable` | Không kết nối được dịch vụ AI |
| 422/503 | (từ dịch vụ AI) | Chuyển tiếp nguyên mã |

### Route kiểm thử `POST /api/chat/crm`

Proxy sang `POST /chat/crm` của dịch vụ AI bằng `CHATBOT_CRM_API_KEY` (key kênh
`crm`), giữ `session_id` trong cookie riêng `qs_crm_session`. Route chỉ bật khi đặt
biến này; không đặt thì trả 404. `user_id` (1–128 ký tự) do trình duyệt gửi và
**không** được xác thực, nên ai gọi được route cũng mạo danh được nhân viên: chỉ
dùng ở môi trường kiểm thử, không bật production. Đổi `user_id` giữa các lượt thì
dịch vụ AI trả `session_not_found` và route tự mở hội thoại mới.

Widget dùng route này khi build với `VITE_CHATBOT_CHANNEL=crm`, `user_id` lấy từ
`VITE_CRM_TEST_USER_ID` (mặc định `employee_test_001`). `crm_access_token` (tùy chọn,
1–4096 ký tự) lấy từ `VITE_CRM_TEST_TOKEN` và được chuyển tiếp nguyên văn cho tool báo
cáo gọi API CRM; route không log giá trị này. Các biến `VITE_*` đặt trong `.env` ở
**gốc repo** (Vite không đọc `widget-backend/.env`) và bị đóng gói vào bundle trình
duyệt: token chỉ dùng cho môi trường kiểm thử.

Log mỗi request chỉ có metadata (`request_id`, route, status, outcome, thời gian);
không log key, nội dung tin nhắn, `visitor_id` hay `session_id`.

Chưa có: rate limit theo khách, docker-compose.
