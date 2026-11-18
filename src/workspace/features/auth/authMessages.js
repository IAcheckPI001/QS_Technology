// Luật mật khẩu phía giao diện (khớp 14.2: tối thiểu 12 ký tự, không trùng email) và cách đổi mã lỗi
// của API đăng nhập thành câu cho người dùng. Server vẫn là nơi kiểm cuối cùng.

import { S } from '../../strings.vi.js';
import { userMessage } from '../../api/errors.js';

export const MIN_PASSWORD_LENGTH = 12;

// Đếm theo ký tự Unicode, không theo đơn vị UTF-16.
const length = (value) => [...(value || '')].length;

/**
 * Kiểm form mật khẩu mới. `current` để undefined khi màn không có ô mật khẩu hiện tại (đặt lại).
 * Trả về { current?, next?, confirm? }; rỗng là hợp lệ.
 */
export function validateNewPassword({ email = '', current, next = '', confirm = '' }) {
  const errors = {};
  if (current !== undefined && !current) errors.current = S.auth.errCurrentRequired;
  if (length(next) < MIN_PASSWORD_LENGTH) errors.next = S.auth.errTooShort;
  else if (email && next.trim().toLowerCase() === email.trim().toLowerCase()) errors.next = S.auth.errEqualsEmail;
  else if (current && next === current) errors.next = S.auth.errReused;
  if (!errors.next && next !== confirm) errors.confirm = S.auth.errMismatch;
  return errors;
}

const FIELD_ERRORS = {
  invalid_current_password: ['current', S.auth.errCurrentWrong],
  password_too_short: ['next', S.auth.errTooShort],
  password_equals_email: ['next', S.auth.errEqualsEmail],
  password_reused: ['next', S.auth.errReused],
};

/** Lỗi API gắn được vào một ô của form mật khẩu → { field, message }; không gắn được → null. */
export function passwordFieldError(error) {
  const match = FIELD_ERRORS[error?.code];
  return match ? { field: match[0], message: match[1] } : null;
}

const RESET_INVALID = new Set(['reset_token_invalid', 'reset_token_expired', 'reset_token_used']);

/** Link đặt lại hết hạn, đã dùng hoặc sai. */
export function isResetLinkInvalid(error) {
  return RESET_INVALID.has(error?.code);
}

/** "14:35", hoặc "14:35 ngày 19/11/2026" khi không cùng ngày. Giá trị hỏng → ''. */
export function formatUnlockTime(iso, now = new Date()) {
  const date = iso ? new Date(iso) : null;
  if (!date || Number.isNaN(date.getTime())) return '';
  const time = date.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
  return date.toDateString() === now.toDateString() ? time : `${time} ngày ${date.toLocaleDateString('vi-VN')}`;
}

/** Lỗi chung của các màn đăng nhập: máy chủ chưa có B1 thì nói rõ thay vì "Not Found". */
export function authErrorMessage(error) {
  if (error?.kind === 'not_found') return S.errors.authUnavailable;
  return userMessage(error);
}

/**
 * Thông báo khi đăng nhập không được (14.3). Sai thông tin luôn dùng một câu chung, không lộ email
 * có tồn tại; backend chỉ báo khoá/vô hiệu theo luật của B1.
 */
export function loginErrorMessage(error, now = new Date()) {
  switch (error?.code) {
    case 'invalid_credentials':
      return S.auth.invalidCredentials;
    case 'account_locked': {
      const when = formatUnlockTime(error.details?.locked_until, now);
      return when ? S.auth.lockedUntil(when) : S.auth.locked;
    }
    case 'account_disabled':
      return S.auth.disabled;
    default:
      return error?.kind === 'unauthorized' ? S.auth.invalidCredentials : authErrorMessage(error);
  }
}
