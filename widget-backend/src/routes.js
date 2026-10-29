import { randomUUID } from 'node:crypto';

import { AiServiceUnreachable } from './ai_client.js';
import {
    SESSION_COOKIE,
    SESSION_MAX_AGE,
    VISITOR_COOKIE,
    VISITOR_MAX_AGE,
    clearCookie,
    isUuid,
    readUuidCookie,
    serializeCookie,
} from './cookies.js';

const MAX_BODY_BYTES = 16 * 1024;

class HttpError extends Error {
    constructor(status, code, message) {
        super(message);
        this.status = status;
        this.code = code;
    }
}

// Lỗi trả trình duyệt cùng dạng với dịch vụ AI: {"detail": {code, message, request_id}}.
function sendJson(res, ctx, status, body) {
    res.writeHead(status, {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'no-store',
        ...(ctx.cookies.length ? { 'Set-Cookie': ctx.cookies } : {}),
    });
    res.end(JSON.stringify(body));
}

function sendError(res, ctx, status, code, message) {
    ctx.outcome = code;
    sendJson(res, ctx, status, { detail: { code, message, request_id: ctx.requestId } });
}

async function readJson(req) {
    const chunks = [];
    let size = 0;
    for await (const chunk of req) {
        size += chunk.length;
        if (size > MAX_BODY_BYTES) throw new HttpError(413, 'payload_too_large', 'Request body is too large.');
        chunks.push(chunk);
    }
    try {
        return JSON.parse(Buffer.concat(chunks).toString('utf8'));
    } catch {
        throw new HttpError(400, 'invalid_json', 'Request body must be valid JSON.');
    }
}

// Event `done` của dịch vụ AI có session_id (cho CRM); widget không cần nên gỡ ra,
// các event khác giữ nguyên. Dịch vụ AI phân tách event bằng "\n\n".
export function stripDoneSessionId(block) {
    const lines = block.split('\n');
    if (!lines.includes('event: done')) return block;
    return lines.map((line) => {
        if (!line.startsWith('data: ')) return line;
        try {
            const { session_id: _sessionId, ...payload } = JSON.parse(line.slice(6));
            return `data: ${JSON.stringify(payload)}`;
        } catch {
            return line;
        }
    }).join('\n');
}

async function pipeSse(body, res) {
    const decoder = new TextDecoder();
    let buffer = '';
    for await (const chunk of body) {
        buffer += decoder.decode(chunk, { stream: true });
        let boundary;
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
            res.write(`${stripDoneSessionId(buffer.slice(0, boundary))}\n\n`);
            buffer = buffer.slice(boundary + 2);
        }
    }
    buffer += decoder.decode();
    if (buffer) res.write(stripDoneSessionId(buffer));
}

async function readDetail(response) {
    try {
        const payload = await response.json();
        return payload?.detail && typeof payload.detail === 'object' && !Array.isArray(payload.detail)
            ? payload.detail
            : {};
    } catch {
        return {};
    }
}

export function createRouter({ config, ai, logger = console }) {
    const cookieOptions = { secure: config.cookieSecure };

    // Chống CSRF: request xác thực bằng cookie chỉ nhận từ origin của widget. Không có
    // Origin (curl, server-to-server) thì không phải request cross-site của trình duyệt.
    function assertOrigin(req) {
        const origin = req.headers.origin;
        if (origin && !config.allowedOrigins.has(origin)) {
            throw new HttpError(403, 'origin_not_allowed', 'This origin is not allowed.');
        }
    }

    function ensureVisitor(req, ctx) {
        if (readUuidCookie(req, VISITOR_COOKIE)) return;
        ctx.cookies.push(serializeCookie(VISITOR_COOKIE, randomUUID(), { ...cookieOptions, maxAge: VISITOR_MAX_AGE }));
    }

    // Lỗi từ dịch vụ AI: lỗi key/cấu hình (401/403) và lỗi server khác 503 không lộ cho trình duyệt.
    async function relayError(res, ctx, upstream, detail) {
        const status = upstream.status;
        const upstreamDetail = detail ?? await readDetail(upstream);
        if (status === 401 || status === 403 || (status >= 500 && status !== 503)) {
            logger.error(
                `AI service request failed status=${status} code=${upstreamDetail.code ?? '-'} `
                + `request_id=${ctx.requestId} ai_request_id=${upstream.headers.get('x-request-id') ?? '-'}`,
            );
            return sendError(res, ctx, 502, 'chat_unavailable', 'Chat is temporarily unavailable. Please try again.');
        }
        return sendError(
            res,
            ctx,
            status,
            upstreamDetail.code ?? `http_${status}`,
            upstreamDetail.message ?? 'Chat request failed.',
        );
    }

    async function postChat(req, res, ctx) {
        assertOrigin(req);
        ensureVisitor(req, ctx);
        const payload = await readJson(req);
        const text = payload?.message?.text;
        if (typeof text !== 'string' || !text.trim()) {
            throw new HttpError(400, 'invalid_request', 'message.text is required.');
        }
        const clientContext = payload.client_context && typeof payload.client_context === 'object'
            ? payload.client_context
            : undefined;
        const idempotencyKey = isUuid(req.headers['idempotency-key']) ? req.headers['idempotency-key'] : undefined;

        // Trình duyệt ngắt → huỷ request tới dịch vụ AI (dịch vụ ghi lượt 'cancelled').
        const controller = new AbortController();
        res.on('close', () => {
            if (!res.writableFinished) controller.abort();
        });
        const send = (sessionId) => ai.chatWebsite({
            sessionId,
            message: { text },
            clientContext,
            idempotencyKey,
            signal: controller.signal,
        });

        let sessionId = readUuidCookie(req, SESSION_COOKIE);
        let upstream = await send(sessionId);
        if (upstream.status === 404 && sessionId) {
            const detail = await readDetail(upstream);
            if (detail.code !== 'session_not_found') return relayError(res, ctx, upstream, detail);
            // Session cũ không còn (hết hạn, bị thu hồi): bắt đầu hội thoại mới một lần.
            ctx.cookies.push(clearCookie(SESSION_COOKIE, cookieOptions));
            sessionId = null;
            upstream = await send(null);
        }
        if (!upstream.ok) return relayError(res, ctx, upstream);

        const nextSessionId = upstream.headers.get('x-session-id');
        if (isUuid(nextSessionId)) {
            // Đặt trước khi stream: sau khi gửi header thì không đặt cookie được nữa.
            ctx.cookies.push(serializeCookie(SESSION_COOKIE, nextSessionId.toLowerCase(), {
                ...cookieOptions,
                maxAge: SESSION_MAX_AGE,
            }));
        }
        res.writeHead(200, {
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache, no-transform',
            'X-Accel-Buffering': 'no',
            ...(ctx.cookies.length ? { 'Set-Cookie': ctx.cookies } : {}),
        });
        try {
            if (upstream.body) await pipeSse(upstream.body, res);
        } catch {
            ctx.outcome = controller.signal.aborted ? 'client_disconnected' : 'ai_stream_interrupted';
        } finally {
            res.end();
        }
    }

    async function getHistory(req, res, ctx) {
        ensureVisitor(req, ctx);
        const sessionId = readUuidCookie(req, SESSION_COOKIE);
        if (!sessionId) return sendJson(res, ctx, 200, { messages: [] });

        const upstream = await ai.history(sessionId);
        if (upstream.status === 404) {
            ctx.cookies.push(clearCookie(SESSION_COOKIE, cookieOptions));
            return sendJson(res, ctx, 200, { messages: [] });
        }
        if (!upstream.ok) return relayError(res, ctx, upstream);
        const data = await upstream.json();
        // Không trả session_id: trình duyệt không cần và không nên thấy giá trị này.
        return sendJson(res, ctx, 200, { messages: Array.isArray(data?.messages) ? data.messages : [] });
    }

    async function postReset(req, res, ctx) {
        assertOrigin(req);
        ensureVisitor(req, ctx);
        ctx.cookies.push(clearCookie(SESSION_COOKIE, cookieOptions));
        res.writeHead(204, { 'Set-Cookie': ctx.cookies });
        res.end();
    }

    const routes = {
        'POST /api/chat': postChat,
        'GET /api/chat/history': getHistory,
        'POST /api/chat/reset': postReset,
        'GET /health': (req, res, ctx) => sendJson(res, ctx, 200, { status: 'ok' }),
    };

    return async function handle(req, res) {
        const started = Date.now();
        const ctx = { requestId: randomUUID(), outcome: 'ok', cookies: [] };
        const path = new URL(req.url ?? '/', 'http://widget.local').pathname;
        res.setHeader('X-Request-ID', ctx.requestId);
        try {
            const route = routes[`${req.method} ${path}`];
            if (!route) throw new HttpError(404, 'not_found', 'Route not found.');
            await route(req, res, ctx);
        } catch (error) {
            if (res.headersSent) {
                ctx.outcome = 'internal_error';
                res.destroy();
            } else if (error instanceof HttpError) {
                sendError(res, ctx, error.status, error.code, error.message);
            } else if (error instanceof AiServiceUnreachable) {
                logger.error(`AI service unreachable request_id=${ctx.requestId}: ${error.cause?.message ?? error.message}`);
                sendError(res, ctx, 502, 'ai_service_unreachable', 'Chat service is unreachable. Please try again.');
            } else if (error?.name === 'AbortError') {
                ctx.outcome = 'client_disconnected';
                res.destroy();
            } else {
                logger.error(`Widget request failed request_id=${ctx.requestId}`, error);
                sendError(res, ctx, 500, 'internal_error', 'Unexpected error. Please try again.');
            }
        } finally {
            // Chỉ metadata: không log key, nội dung tin nhắn, visitor_id hay session_id.
            logger.info(
                `widget_request request_id=${ctx.requestId} method=${req.method} path=${path} `
                + `status=${res.statusCode} outcome=${ctx.outcome} duration_ms=${Date.now() - started}`,
            );
        }
    };
}
