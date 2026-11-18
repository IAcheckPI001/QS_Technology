// Dữ liệu giả cho đăng nhập khi chưa có B1 (chỉ dev, VITE_WORKSPACE_FIXTURES=1).
// Không phải tính năng: trạng thái lưu trong sessionStorage của trình duyệt.
// Kịch bản (ghi cả ở màn đăng nhập khi chạy dev, FIXTURE_HINTS):
// - mật khẩu từ 12 ký tự là đúng, ngắn hơn là sai;
// - email chứa "khoa" → tài khoản tạm khoá 15 phút; chứa "vohieu" → bị vô hiệu;
// - email bắt đầu bằng "doimk" → phải đổi mật khẩu sau khi đăng nhập;
// - link đặt lại: token "demo" hợp lệ, token khác coi như hết hạn hoặc đã dùng.

import { ApiError } from '../errors.js';
import { PERMISSIONS } from '../../auth/permissions.js';

const SIGNED_OUT = 'ws.fixture.signedOut';
const SESSION = 'ws.fixture.session';
const VALID_RESET_TOKEN = 'demo';

export const FIXTURE_USER = {
  id: 'fixture-admin',
  email: 'admin@qstcnc.com',
  display_name: 'Quản trị viên',
  role: 'admin',
  permissions: Object.values(PERMISSIONS),
  must_change_password: false,
};

export const FIXTURE_HINTS = [
  'Mật khẩu từ 12 ký tự là đúng.',
  'Email chứa “khoa” → tạm khoá; chứa “vohieu” → bị vô hiệu.',
  'Email bắt đầu bằng “doimk” → bắt đổi mật khẩu.',
  'Link đặt lại thử: /reset-password?token=demo',
];

function read(key) {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key, value) {
  try {
    if (value === null) sessionStorage.removeItem(key);
    else sessionStorage.setItem(key, value);
  } catch {
    /* Trình duyệt chặn storage: bỏ qua, chỉ ảnh hưởng dữ liệu giả. */
  }
}

function currentUser() {
  let session = {};
  try {
    session = JSON.parse(read(SESSION) || '{}') || {};
  } catch {
    session = {};
  }
  return { ...FIXTURE_USER, email: session.email || FIXTURE_USER.email, must_change_password: Boolean(session.mustChange) };
}

function saveUser(user) {
  write(SESSION, JSON.stringify({ email: user.email, mustChange: user.must_change_password }));
}

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const fail = (status, kind, code, message, details) => new ApiError({ status, kind, code, message, details });
const length = (value) => [...(value || '')].length;

export const fixtureAuth = {
  async me() {
    await delay(150);
    if (read(SIGNED_OUT) === '1') throw fail(401, 'unauthorized', 'not_authenticated');
    return { user: currentUser() };
  },

  async login({ email = '', password = '' }) {
    await delay(300);
    const normalized = email.trim().toLowerCase();
    // Giống backend dự kiến: sai thông tin thì thông báo chung, không lộ email có tồn tại.
    if (length(password) < 12) throw fail(401, 'unauthorized', 'invalid_credentials', 'Email hoặc mật khẩu không đúng.');
    if (normalized.includes('khoa')) {
      const lockedUntil = new Date(Date.now() + 15 * 60 * 1000).toISOString();
      throw fail(423, 'unknown', 'account_locked', 'Tài khoản đang tạm khoá.', { locked_until: lockedUntil });
    }
    if (normalized.includes('vohieu')) throw fail(403, 'forbidden', 'account_disabled', 'Tài khoản đã bị vô hiệu.');
    const user = { ...FIXTURE_USER, email: normalized || FIXTURE_USER.email, must_change_password: normalized.startsWith('doimk') };
    saveUser(user);
    write(SIGNED_OUT, null);
    return { user };
  },

  async logout() {
    await delay(100);
    write(SIGNED_OUT, '1');
    write(SESSION, null);
    return null;
  },

  async changePassword({ current_password: current = '', new_password: next = '' }) {
    await delay(300);
    if (length(current) < 12) throw fail(400, 'validation', 'invalid_current_password', 'Mật khẩu hiện tại không đúng.');
    if (length(next) < 12) throw fail(422, 'validation', 'password_too_short', 'Mật khẩu quá ngắn.');
    if (next === current) throw fail(422, 'validation', 'password_reused', 'Mật khẩu mới trùng mật khẩu cũ.');
    const user = { ...currentUser(), must_change_password: false };
    saveUser(user);
    return { user };
  },

  async verifyReset({ token }) {
    await delay(200);
    if (token !== VALID_RESET_TOKEN) throw fail(410, 'unknown', 'reset_token_invalid', 'Link đặt lại không còn hiệu lực.');
    return { email: 'kythuat@qstcnc.com' };
  },

  async resetPassword({ token, new_password: next = '' }) {
    await delay(300);
    if (token !== VALID_RESET_TOKEN) throw fail(410, 'unknown', 'reset_token_invalid', 'Link đặt lại không còn hiệu lực.');
    if (length(next) < 12) throw fail(422, 'validation', 'password_too_short', 'Mật khẩu quá ngắn.');
    return null;
  },
};
