import { afterEach, describe, expect, it, vi } from 'vitest';
import { buildUrl, readCookie, request, setUnauthorizedHandler } from './client.js';
import { ApiError, userMessage } from './errors.js';

function jsonResponse(status, body, headers = {}) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } });
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = 'ws_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT';
});

describe('buildUrl', () => {
  it('bỏ giá trị rỗng và lặp mảng', () => {
    expect(buildUrl('/x', { a: 'b', empty: '', none: null, list: [1, 2] })).toBe('/x?a=b&list=1&list=2');
    expect(buildUrl('/x', { empty: '' })).toBe('/x');
  });
});

describe('readCookie', () => {
  it('đọc đúng cookie theo tên', () => {
    expect(readCookie('ws_csrf', 'a=1; ws_csrf=tok%3D1; b=2')).toBe('tok=1');
    expect(readCookie('missing', 'a=1')).toBe('');
  });
});

describe('request', () => {
  it('gửi cookie và gắn X-CSRF-Token cho POST, không gắn cho GET', async () => {
    document.cookie = 'ws_csrf=abc';
    const fetchMock = vi.fn(async () => jsonResponse(200, { ok: true }));
    vi.stubGlobal('fetch', fetchMock);

    await request('POST', '/workspace/x', { body: { a: 1 } });
    await request('GET', '/workspace/x');

    const [, postInit] = fetchMock.mock.calls[0];
    expect(postInit.credentials).toBe('include');
    expect(postInit.headers['X-CSRF-Token']).toBe('abc');
    expect(postInit.body).toBe('{"a":1}');
    const [, getInit] = fetchMock.mock.calls[1];
    expect(getInit.headers['X-CSRF-Token']).toBeUndefined();
  });

  it('chuyển lỗi backend thành ApiError có code và request id', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(409, { detail: { code: 'name_taken', message: 'Trùng tên' } }, { 'X-Request-ID': 'req-1' })));
    const error = await request('POST', '/x', { body: {} }).catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, code: 'name_taken', kind: 'conflict', requestId: 'req-1', message: 'Trùng tên' });
  });

  it('giữ trường thêm của detail (vd. locked_until)', async () => {
    const detail = { code: 'account_locked', message: 'Khoá', locked_until: '2026-11-18T08:15:00Z' };
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(423, { detail })));
    const error = await request('POST', '/x', { body: {} }).catch((e) => e);
    expect(error).toMatchObject({ code: 'account_locked', message: 'Khoá', details: { locked_until: '2026-11-18T08:15:00Z' } });
  });

  it('401 gọi handler hết phiên, trừ khi skipAuthRedirect', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(401, { detail: { code: 'not_authenticated', message: 'x' } })));
    const handler = vi.fn();
    const off = setUnauthorizedHandler(handler);
    await request('GET', '/x').catch(() => {});
    await request('GET', '/x', { skipAuthRedirect: true }).catch(() => {});
    off();
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it('lỗi mạng và 5xx dùng thông báo dễ hiểu, không lộ chi tiết kỹ thuật', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch'); }));
    const network = await request('GET', '/x').catch((e) => e);
    expect(network.kind).toBe('network');
    expect(userMessage(network)).toMatch(/Không kết nối được/);

    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(503, { detail: { code: 'database_unavailable', message: 'Postgres down' } })));
    const server = await request('GET', '/x').catch((e) => e);
    expect(server.kind).toBe('server');
    expect(userMessage(server)).not.toMatch(/Postgres/);
  });
});
