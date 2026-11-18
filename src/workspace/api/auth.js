// Đăng nhập Workspace. Contract theo thiết kế B1 (FRONTEND_REQUIREMENTS.md mục 14), backend CHƯA có;
// đường dẫn, mã lỗi chốt lại khi làm B1 (README luồng workspace-ui, mục Contract):
// - GET  /workspace/auth/me → { user }
// - POST /workspace/auth/login { email, password } → { user }
// - POST /workspace/auth/logout
// - POST /workspace/auth/change-password { current_password, new_password } → { user }
// - POST /workspace/auth/password-reset/verify { token } → { email }
// - POST /workspace/auth/password-reset { token, new_password }
// `user` = { id, email, display_name, role, permissions[], must_change_password }.
// Bật VITE_WORKSPACE_FIXTURES=1 (chỉ dev) để chạy với dữ liệu giả.

import { USE_FIXTURES } from '../config.js';
import { api } from './client.js';
import { fixtureAuth } from './fixtures/auth.js';

// Các lệnh dùng khi chưa có phiên tự xử lý 401 (sai mật khẩu), không chuyển trang. Đổi mật khẩu
// cần phiên: 401 ở đó là hết phiên nên vẫn về đăng nhập; sai mật khẩu hiện tại trả 400
// `invalid_current_password`.
const own = (options) => ({ ...options, skipAuthRedirect: true });

const real = {
  me: (options) => api.get('/workspace/auth/me', own(options)),
  login: (credentials, options) => api.post('/workspace/auth/login', credentials, own(options)),
  logout: (options) => api.post('/workspace/auth/logout', undefined, options),
  changePassword: (body, options) => api.post('/workspace/auth/change-password', body, options),
  verifyReset: (body, options) => api.post('/workspace/auth/password-reset/verify', body, own(options)),
  resetPassword: (body, options) => api.post('/workspace/auth/password-reset', body, own(options)),
};

export const authApi = USE_FIXTURES ? fixtureAuth : real;
