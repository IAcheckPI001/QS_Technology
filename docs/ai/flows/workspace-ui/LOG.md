# Nhật ký luồng workspace-ui

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính và trỏ tới nó. Khi file vượt 300 dòng, cắt các mục cũ
sang `LOG-archive-<ngày của mục mới nhất bị cắt>.md` và để lại liên kết ở đầu file.

Sau khi thêm mục, viết lại [STATE.md](STATE.md).

## 2026-11-18 · Chốt cách lấy giờ hỏi (W3) · loại: quyết định

- Vấn đề: `chat_history` ghi một dòng lúc lượt kết thúc nên không có giờ hỏi (FRONTEND_REQUIREMENTS 19.2 W3).
- Quyết định/luật (Toma): `asked_at = created_at − latency_ms`, tính khi đọc; không thêm cột `asked_at`. Thiếu `latency_ms` thì `asked_at = null`.
- File: `docs/ai/FRONTEND_REQUIREMENTS.md` (19.2, 19.7, Trạng thái), STATE luồng này.
- Kiểm chứng: `check_ai_docs.py` → đạt.
- Ảnh hưởng contract/API/schema: không đổi schema; trường `asked_at` của `/history` theo cách tính này.
- Mở tiếp: WU-7 (làm backend B2/B5).

## 2026-11-18 · Đặc tả API hội thoại cho GĐ 2 (B2, B5, registry model) · loại: quyết định

- Vấn đề: màn hội thoại v1 cần lọc/tìm trên toàn bộ dữ liệu, phân trang, chỉ số theo bộ lọc, tài liệu đã dùng theo từng lượt; API hiện trả hết, chỉ xét lượt cuối, chỉ số tính toàn bảng (F8).
- Quyết định/luật (đề xuất, Toma yêu cầu ghi đặc tả): FRONTEND_REQUIREMENTS mục 19.
  - 6 API đọc: sửa `/chatbot/conversations`, `/history`, `/retrieval`; mới `/conversations/metrics`, `/conversations/{id}`, `/product-models`.
  - 3 sửa luồng ghi: lưu nguồn của chunk vào snapshot (W1), mã lỗi nhà cung cấp trong span LLM (W2), giờ hỏi (W3, cần chốt).
  - Chỉ thêm, không gửi `limit` thì trả như cũ để `/legacy` chạy tới GĐ 6.
- Căn cứ: đối chiếu `backend/sql/*.sql`, `db/models/*.py`, `services/chat_service.py` (ghi một dòng `chat_history` lúc lượt kết thúc; `_retrieval_snapshot` bỏ `doc_id`/`section_title`), `repositories/history_repository.py` (`list_conversations`, `aggregate_metrics`).
- File: `docs/ai/FRONTEND_REQUIREMENTS.md` (mục 19, bảng B2/B5, Trạng thái, 18.4), `docs/ai/api_guidelines.md` (trỏ tới mục 19), README và STATE luồng này.
- Kiểm chứng: `check_ai_docs.py` → đạt.
- Ảnh hưởng contract/API/schema: chưa đổi code; khi làm, route thuộc chat-platform phải cập nhật api_guidelines và test (TR-06).
- Mở tiếp: WU-7 (chốt W3, làm backend).

## 2026-11-18 · GĐ 1: đăng nhập, đổi mật khẩu bắt buộc, đặt lại mật khẩu (giao diện) · loại: thay đổi

- Vấn đề: GĐ 0 chỉ có trang đăng nhập tạm; 14.3 cần đăng nhập, đổi mật khẩu bắt buộc, đặt lại từ link admin.
- Quyết định/luật:
  - màn đăng nhập theo mock M1 (Main, MobileLogin); không điền sẵn email mẫu như mock;
  - sai thông tin: một câu chung; khoá: kèm giờ mở nếu backend gửi `locked_until`; vô hiệu: bảo liên hệ admin;
  - `must_change_password` → `RequireAuth` chuyển mọi trang sang `/change-password?next=…`; nút phụ là Đăng xuất;
  - link đặt lại được kiểm ngay khi mở; đặt xong về đăng nhập với email điền sẵn;
  - kiểm mật khẩu ở trình duyệt theo 14.2 (≥ 12 ký tự, không trùng email, khác mật khẩu cũ, nhập lại khớp); server vẫn kiểm cuối;
  - đổi mật khẩu không bỏ qua xử lý 401 (401 = hết phiên); sai mật khẩu hiện tại dự kiến là 400 `invalid_current_password`.
- File:
  - `src/workspace/features/auth/` (LoginPage, ChangePasswordPage, ResetPasswordPage, AuthLayout, NewPasswordFields, usePasswordForm, authMessages, auth.module.css, auth.test.jsx);
  - `api/auth.js`, `api/fixtures/auth.js` (kịch bản giả), `api/errors.js` (giữ trường thêm của `detail`);
  - `auth/` (guard bắt đổi mật khẩu, `setUser`, `changePasswordPath`); `components/ui.jsx` (`PasswordField`, banner thành công);
  - `WorkspaceApp.jsx` (route `/reset-password`, `/change-password`); bỏ `pages/LoginPlaceholderPage.jsx`.
- Kiểm chứng: `npm test` → 43 test đạt; eslint code Workspace → 0 lỗi; `npm run build` → đạt; preview 5174 ở 320px và 1280×800 → đạt (STATE.md).
- Ảnh hưởng contract/API/schema: không đổi backend. Contract B1 giả định ghi ở README mục Contract (WU-4).
- Mở tiếp: WU-4, WU-5, WU-6; GĐ 2.

## 2026-11-18 · GĐ 0: khung app, lớp API, đăng nhập phía giao diện, component dùng chung · loại: thay đổi

- Vấn đề: chưa có nền để dựng giao diện v1 (mock version 47); `App.jsx` chỉ có bản Workspace cũ.
- Quyết định/luật (duyệt: Toma, FRONTEND_REQUIREMENTS.md 18.6):
  - thêm Vitest + Testing Library + jsdom (devDependencies; `@testing-library/dom` là gói bắt buộc đi kèm);
  - Workspace mới ở `/`, bản cũ ở `/legacy`;
  - dữ liệu giả `VITE_WORKSPACE_FIXTURES` chỉ khi chạy dev;
  - v1 chỉ tiếng Việt;
  - mở luồng tài liệu này.
- Quyết định thêm: lớp API dùng `fetch` thay vì `axios`. `npm audit` báo nhiều cảnh báo cho `axios` ^1.11 đang có; không thêm gói mới.
- File:
  - `src/workspace/**` (config, strings, tokens, api, auth, hooks, components, layout, pages, test);
  - `src/App.jsx`, `vite.config.js` (proxy `/workspace`, `/chatbot`; cấu hình test), `index.html` (tiếng Việt, font Inter, tiêu đề);
  - `package.json` (script `test`, devDependencies), `package-lock.json`;
  - `.claude/vite.worktree.config.js` (preview bật dữ liệu giả).
- Kiểm chứng:
  - `npm test` → 27 test đạt;
  - `npx eslint src/workspace src/App.jsx vite.config.js` → 0 lỗi;
  - `npm run build` → đạt;
  - preview 5174 ở 335px và 1280×800 → đạt (STATE.md).
- Ảnh hưởng contract/API/schema: không đổi backend. Frontend giả định contract đăng nhập B1 (`/workspace/auth/*`, cookie `ws_csrf`), chốt khi làm B1.
- Mở tiếp: WU-1 (lint có sẵn), WU-2 (axios), WU-3, WU-4; GĐ 1, GĐ 2.
