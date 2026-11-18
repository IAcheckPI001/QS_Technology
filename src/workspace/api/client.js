// Lớp gọi API của Workspace (mục 18.2). Dùng fetch có sẵn của trình duyệt, không qua axios:
// - gửi cookie phiên (credentials: 'include');
// - tự gắn X-CSRF-Token cho POST/PATCH/PUT/DELETE;
// - 401 gọi handler do AuthProvider đăng ký (về /login?next=…), các lỗi khác ném ApiError.

import { API_BASE, CSRF_COOKIE, CSRF_HEADER } from '../config.js';
import { ApiError, errorFromResponse } from './errors.js';

const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);
let unauthorizedHandler = null;

/** AuthProvider đăng ký hàm xử lý hết phiên; trả về hàm huỷ đăng ký. */
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
  return () => {
    if (unauthorizedHandler === handler) unauthorizedHandler = null;
  };
}

export function readCookie(name, cookieString = typeof document === 'undefined' ? '' : document.cookie) {
  for (const part of cookieString.split(';')) {
    const [key, ...rest] = part.trim().split('=');
    if (key === name) return decodeURIComponent(rest.join('='));
  }
  return '';
}

/** Ghép query string, bỏ giá trị rỗng/null; mảng thành nhiều tham số cùng tên. */
export function buildUrl(path, params) {
  const url = `${API_BASE}${path}`;
  if (!params) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    if (Array.isArray(value)) value.forEach((item) => search.append(key, String(item)));
    else search.append(key, String(value));
  }
  const query = search.toString();
  return query ? `${url}?${query}` : url;
}

export async function request(method, path, { params, body, signal, skipAuthRedirect = false } = {}) {
  const upper = method.toUpperCase();
  const headers = { Accept: 'application/json' };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  if (UNSAFE.has(upper)) {
    const token = readCookie(CSRF_COOKIE);
    if (token) headers[CSRF_HEADER] = token;
  }

  let response;
  try {
    response = await fetch(buildUrl(path, params), {
      method: upper,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: 'include',
      signal,
    });
  } catch (cause) {
    if (cause && cause.name === 'AbortError') throw new ApiError({ kind: 'aborted', message: 'aborted' });
    throw new ApiError({ kind: 'network' });
  }

  if (!response.ok) {
    const error = await errorFromResponse(response);
    if (error.kind === 'unauthorized' && !skipAuthRedirect && unauthorizedHandler) unauthorizedHandler(error);
    throw error;
  }
  if (response.status === 204) return null;
  const type = response.headers.get('Content-Type') || '';
  return type.includes('application/json') ? response.json() : response.text();
}

export const api = {
  get: (path, options) => request('GET', path, options),
  post: (path, body, options) => request('POST', path, { ...options, body }),
  patch: (path, body, options) => request('PATCH', path, { ...options, body }),
  del: (path, options) => request('DELETE', path, options),
};
