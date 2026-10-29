// Cookie của widget: đều HttpOnly nên JavaScript (kể cả XSS) không đọc được.
export const VISITOR_COOKIE = 'qs_visitor';
export const SESSION_COOKIE = 'qs_chat_session';

export const VISITOR_MAX_AGE = 365 * 24 * 3600;
export const SESSION_MAX_AGE = 30 * 24 * 3600;

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const isUuid = (value) => typeof value === 'string' && UUID_RE.test(value);

export function parseCookies(header) {
    const cookies = {};
    for (const part of (header ?? '').split(';')) {
        const separator = part.indexOf('=');
        if (separator < 0) continue;
        const name = part.slice(0, separator).trim();
        if (name && !(name in cookies)) cookies[name] = part.slice(separator + 1).trim();
    }
    return cookies;
}

// Chỉ nhận UUID: giá trị lạ (bị sửa tay, cookie cũ) coi như không có.
export function readUuidCookie(req, name) {
    const value = parseCookies(req.headers.cookie)[name];
    return isUuid(value) ? value.toLowerCase() : null;
}

export function serializeCookie(name, value, { maxAge, secure }) {
    const parts = [`${name}=${value}`, 'Path=/api', 'HttpOnly', 'SameSite=Lax', `Max-Age=${maxAge}`];
    if (secure) parts.push('Secure');
    return parts.join('; ');
}

export const clearCookie = (name, { secure }) => serializeCookie(name, '', { maxAge: 0, secure });
