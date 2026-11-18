// Lỗi API thống nhất cho Workspace. Backend trả `{"detail": {"code", "message"}}` (api_guidelines.md)
// và header `X-Request-ID`; màn hình chỉ cần `kind` để chọn cách báo, không đọc mã HTTP rải rác.

import { S } from '../strings.vi.js';

export class ApiError extends Error {
  constructor({ status = 0, code = '', message = '', requestId = '', kind = 'unknown', details = {} } = {}) {
    super(message || S.errors.unknown);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    // Trường thêm trong `detail` ngoài code/message (vd. `locked_until` khi tài khoản bị khoá).
    this.details = details;
    // network | unauthorized | forbidden | not_found | validation | conflict | server | aborted | unknown
    this.kind = kind;
  }
}

export function kindForStatus(status) {
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'not_found';
  if (status === 409) return 'conflict';
  if (status === 400 || status === 422) return 'validation';
  if (status >= 500) return 'server';
  return 'unknown';
}

/** Thông báo cho người dùng không chuyên kỹ thuật; message của backend dùng cho lỗi nghiệp vụ (4xx). */
export function userMessage(error) {
  if (!(error instanceof ApiError)) return S.errors.unknown;
  if (error.kind === 'network') return S.errors.network;
  if (error.kind === 'server') return S.errors.server;
  if (error.kind === 'forbidden') return S.errors.forbidden;
  return error.message || S.errors.unknown;
}

/** Dựng ApiError từ Response đã nhận (status ngoài 2xx). */
export async function errorFromResponse(response) {
  let body = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  const detail = body && typeof body === 'object' ? body.detail : null;
  const isObject = detail && typeof detail === 'object' && !Array.isArray(detail);
  const { code = '', message = '', ...details } = isObject ? detail : {};
  return new ApiError({
    status: response.status,
    code,
    message: isObject ? message : typeof detail === 'string' ? detail : '',
    details,
    requestId: response.headers.get('X-Request-ID') || '',
    kind: kindForStatus(response.status),
  });
}
