# Nhật ký luồng workspace-ui

Nhật ký phát triển, **mục mới nhất ở trên**. Chỉ thêm mục mới, không sửa mục cũ; nếu mục
cũ sai, thêm mục mới đính chính và trỏ tới nó. Khi file vượt 300 dòng, cắt các mục cũ
sang `LOG-archive-<ngày của mục mới nhất bị cắt>.md` và để lại liên kết ở đầu file.

Sau khi thêm mục, viết lại [STATE.md](STATE.md).

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
