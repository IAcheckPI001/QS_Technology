# Luồng workspace-ui (`src/workspace/`)

Thiết kế của luồng. Sửa khi thiết kế đổi; trạng thái ghi ở [STATE.md](STATE.md), lịch sử
ghi ở [LOG.md](LOG.md). Giới hạn: 200 dòng.

## Phạm vi

Giao diện **QS AI Workspace** cho admin, kỹ thuật viên, reviewer:
- lịch sử hội thoại, chi tiết, diễn biến xử lý;
- kho tài liệu và duyệt đoạn;
- khóa dịch vụ AI;
- tài khoản, đăng nhập.

Yêu cầu, quyết định (Q1–Q27) và kế hoạch theo giai đoạn nằm ở
[FRONTEND_REQUIREMENTS.md](../../FRONTEND_REQUIREMENTS.md); giao diện chuẩn là canvas mock
version 47.

Luồng này **không** gồm:
- widget chat cho khách (`src/chatbot/`, `widget-backend/`, luồng website-qa);
- API backend: route mới thuộc chat-platform và luồng tương ứng.

## Điểm vào

| Loại | Vị trí | Ghi chú |
|---|---|---|
| Route `/*` | `src/App.jsx` → `src/workspace/WorkspaceApp.jsx` | Workspace mới |
| Route `/legacy/*` | `src/pages/SupportWorkspace.jsx` | Bản cũ, xoá ở GĐ 6 |
| Dev server | `npm run dev` (5173), preview worktree `.claude/vite.worktree.config.js` (5174, bật dữ liệu giả) | Vite proxy `/workspace`, `/chatbot` → `:8000`, `/api` → `:8787` |

## Cấu trúc

| Vùng | File | Vai trò |
|---|---|---|
| Khởi tạo | `WorkspaceApp.jsx` | Providers (Toast, Auth), định tuyến, chặn route theo quyền |
| Cấu hình, chữ | `config.js`, `strings.vi.js`, `styles/tokens.css` | Biến môi trường; chuỗi tiếng Việt; token màu Q21 và đặt lại CSS chung trong `.ws-root` |
| API | `api/client.js`, `api/errors.js`, `api/<tài nguyên>.js`, `api/fixtures/` | `fetch` + cookie + CSRF; `ApiError` theo `kind`; mỗi tài nguyên một file; dữ liệu giả |
| Đăng nhập | `auth/` | `AuthProvider` (`/me`, 401 → `/login?next=`), `RequireAuth` (kể cả bắt đổi mật khẩu), `RequirePermission`, `can()`, `safeNext()` |
| Màn đăng nhập | `features/auth/` | `/login` (M1), `/change-password`, `/reset-password?token=`; luật mật khẩu và câu báo lỗi ở `authMessages.js` |
| Hook | `hooks/` | `useResource`, `useCursorList` (Q26), `useUrlFilters`, `useLocalStorage` |
| Component | `components/` | `ui.jsx` (Button, IconButton, Badge, Card, TextField, PasswordField, SelectField, EmptyState, Skeleton, ErrorBanner, LoadMore, PageHeader), `Modal`, `ConfirmDialog`, `toast/` |
| Khung | `layout/` | `AppShell` (sidebar Q22, thanh trên + thanh dưới ≤ 720px, widget chat thử), `navItems.js` |
| Trang | `pages/` | 404, Không đủ quyền, màn chưa dựng |
| Màn nghiệp vụ | `features/<màn>/` | Mỗi màn một thư mục (trang, hook, CSS, test) |

## Contract

API backend: [api_guidelines.md](../../api_guidelines.md).
- **Lỗi:** `{"detail": {"code", "message"}}` + header `X-Request-ID`. `api/errors.js` chuyển thành `ApiError.kind`: `network | unauthorized | forbidden | not_found | validation | conflict | server | aborted`.
- **Đăng nhập (B1, chưa có backend; frontend giả định, chốt khi làm B1):**

  | Route | Body → kết quả | Lỗi giao diện xử lý |
  |---|---|---|
  | `GET /workspace/auth/me` | → `{ user }` | 401 = chưa đăng nhập; 404 = máy chủ chưa có B1 |
  | `POST /workspace/auth/login` | `{ email, password }` → `{ user }` | 401 `invalid_credentials`; 423 `account_locked` + `locked_until`; 403 `account_disabled` |
  | `POST /workspace/auth/logout` | → 204 | |
  | `POST /workspace/auth/change-password` | `{ current_password, new_password }` → `{ user }` | 400 `invalid_current_password`; 422 `password_too_short`, `password_equals_email`, `password_reused`; 401 = hết phiên |
  | `POST /workspace/auth/password-reset/verify` | `{ token }` → `{ email }` | `reset_token_invalid` (hoặc `_expired`, `_used`) |
  | `POST /workspace/auth/password-reset` | `{ token, new_password }` → 204 | như trên + lỗi mật khẩu 422 |

  `user` = `{ id, email, display_name, role, permissions[], must_change_password }`. Trường thêm của lỗi
  nằm trong `detail` cạnh `code`, `message`. Cookie phiên HttpOnly; CSRF đọc từ cookie `ws_csrf`, gửi lại
  qua header `X-CSRF-Token`. Token đặt lại đi trong body POST, không đi trong đường dẫn API.
- **Hội thoại (có sẵn):** `GET /chatbot/conversations`, `/chatbot/sessions/{id}/history`, `/retrieval`, `/trace`.
- **Phân trang (B2):** con trỏ `{ items, next_cursor, total? }` (Q26).

## Bất biến của luồng

- Màn hình không gọi `fetch`/`axios` trực tiếp, chỉ qua `api/<tài nguyên>.js`. Không dùng `axios` trong Workspace (gói có cảnh báo bảo mật, 2026-11-18).
- Kiểm **quyền** bằng `can(user, permission)`, không kiểm tên vai trò.
- Tìm và lọc chạy ở server trên toàn bộ dữ liệu; danh sách dài phân trang con trỏ (Q26).
- Lớp phủ (cửa sổ, sheet, dropdown) bắt phím trên chính nó, giữ focus bên trong, trả focus khi đóng.
- Không lộ chữ kỹ thuật cho người dùng không chuyên kỹ thuật: thông số kỹ thuật nằm trong phần "Chi tiết kỹ thuật" (Q23, Q27).
- Dữ liệu giả chỉ bật khi chạy dev; màn chạy trên dữ liệu giả không được báo là xong (TR-10).
- Một bộ component đáp ứng mọi cỡ màn, không làm app điện thoại riêng; ≤ 720px là bố cục điện thoại.

## Cấu hình

| Biến hoặc file | Mặc định | Tác dụng |
|---|---|---|
| `VITE_WORKSPACE_API_URL` | rỗng (cùng origin) | Gốc URL dịch vụ AI; để trống để cookie đi cùng domain |
| `VITE_WORKSPACE_FIXTURES` | tắt | `1` + chạy dev: đăng nhập (và các màn chưa có API) dùng dữ liệu giả; kịch bản ghi ở `api/fixtures/auth.js` và hiện dưới màn đăng nhập |
| `localStorage['ws.sidebarCollapsed']` | `false` | Sidebar thu gọn (Q22) |

## Test và eval

Từ thư mục gốc repo:

```powershell
npm test          # Vitest + Testing Library (jsdom)
npm run lint
npm run build
```

Test đặt cạnh code (`*.test.js(x)`); `src/workspace/test/setup.js` dọn DOM sau mỗi test.

## Ranh giới với luồng khác

- **Widget chat:** dùng lại `src/components/ChatbotWidget.jsx` làm nút chat thử, không sửa.
- **Backend:** mỗi giai đoạn cần một việc backend (B1, B2, B5, B6, B7), làm ở chat-platform và các luồng liên quan.
- **Cây mục ở màn duyệt tài liệu:** phụ thuộc chất lượng `section_path` của doc-ingest (lỗi T-07).

## Tài liệu sâu hơn

- [FRONTEND_REQUIREMENTS.md](../../FRONTEND_REQUIREMENTS.md): mục 13 (quyết định), 14 (đăng nhập), 15 (backend tài liệu), 18 (kế hoạch).
