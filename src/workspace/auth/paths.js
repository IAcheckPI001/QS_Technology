export const LOGIN_PATH = '/login';
export const CHANGE_PASSWORD_PATH = '/change-password';
export const HOME_PATH = '/conversations';

function withNext(base, location) {
  const next = `${location.pathname}${location.search}`;
  const skip = !next || next === '/' || next.startsWith(LOGIN_PATH) || next.startsWith(CHANGE_PASSWORD_PATH);
  return skip ? base : `${base}?next=${encodeURIComponent(next)}`;
}

/** Đường dẫn đăng nhập kèm `next` để quay lại trang đang xem sau khi đăng nhập (mục 14.3). */
export function loginPath(location) {
  return withNext(LOGIN_PATH, location);
}

/** Đường dẫn đổi mật khẩu bắt buộc, giữ trang định mở để chuyển tới sau khi đổi xong. */
export function changePasswordPath(location) {
  return withNext(CHANGE_PASSWORD_PATH, location);
}

/** Chỉ nhận `next` là đường dẫn nội bộ (bắt đầu bằng một dấu /), chống chuyển hướng ra site khác. */
export function safeNext(next, fallback = HOME_PATH) {
  return typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') && !next.startsWith('/\\') ? next : fallback;
}
