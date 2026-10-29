import assert from 'node:assert/strict';
import http from 'node:http';
import { after, before, beforeEach, describe, test } from 'node:test';

import { createWidgetServer } from '../src/server.js';

const API_KEY = 'qsk_0123456789abcdef_' + 'a'.repeat(43);
const ORIGIN = 'http://localhost:5173';
const SESSION_A = '11111111-1111-4111-8111-111111111111';
const SESSION_B = '22222222-2222-4222-8222-222222222222';
const SSE_BODY = 'event: delta\ndata: {"text":"Xin chào"}\n\nevent: done\ndata: {"request_id":"r1"}\n\n';

const listen = (server) => new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => resolve(server.address().port));
});

// Dịch vụ AI giả: ghi lại request, trả lời theo `ai.reply` của từng test.
const ai = { requests: [], reply: null };
const aiServer = http.createServer(async (req, res) => {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const raw = Buffer.concat(chunks).toString('utf8');
    const request = { method: req.method, url: req.url, headers: req.headers, body: raw ? JSON.parse(raw) : null };
    ai.requests.push(request);
    ai.reply(request, res);
});

const sse = (sessionId) => (request, res) => {
    res.writeHead(200, { 'Content-Type': 'text/event-stream', 'X-Session-ID': sessionId });
    res.end(SSE_BODY);
};

const json = (status, body) => (request, res) => {
    res.writeHead(status, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify(body));
};

const logs = [];
const logger = { info: (line) => logs.push(line), error: (line) => logs.push(line) };
let widget;
let widgetPort;
let aiPort;

function call(path, { method = 'GET', headers = {}, body } = {}) {
    return new Promise((resolve, reject) => {
        const payload = body === undefined ? undefined : (typeof body === 'string' ? body : JSON.stringify(body));
        const req = http.request({
            host: '127.0.0.1',
            port: widgetPort,
            path,
            method,
            headers: {
                ...(payload ? { 'Content-Type': 'application/json' } : {}),
                ...headers,
            },
        }, (res) => {
            const chunks = [];
            res.on('data', (chunk) => chunks.push(chunk));
            res.on('end', () => resolve({
                status: res.statusCode,
                headers: res.headers,
                text: Buffer.concat(chunks).toString('utf8'),
                cookies: res.headers['set-cookie'] ?? [],
            }));
        });
        req.on('error', reject);
        if (payload) req.write(payload);
        req.end();
    });
}

const chat = (headers = {}, body = { message: { text: 'Địa chỉ công ty?' } }) => (
    call('/api/chat', { method: 'POST', headers: { Origin: ORIGIN, ...headers }, body })
);

const cookieValue = (cookies, name) => {
    const cookie = cookies.find((item) => item.startsWith(`${name}=`));
    return cookie === undefined ? undefined : cookie.slice(name.length + 1).split(';')[0];
};

before(async () => {
    aiPort = await listen(aiServer);
    widget = createWidgetServer({
        port: 0,
        aiServiceUrl: `http://127.0.0.1:${aiPort}`,
        apiKey: API_KEY,
        allowedOrigins: new Set([ORIGIN]),
        cookieSecure: false,
        aiResponseTimeoutMs: 5000,
    }, { logger });
    widgetPort = await listen(widget);
});

after(() => {
    widget.close();
    aiServer.close();
});

beforeEach(() => {
    ai.requests = [];
    ai.reply = sse(SESSION_A);
    logs.length = 0;
});

describe('POST /api/chat', () => {
    test('new visitor gets HttpOnly cookies and AI gets service key without visitor id', async () => {
        const response = await chat({}, { message: { text: 'Địa chỉ công ty?' }, visitor_id: 'spoofed' });

        assert.equal(response.status, 200);
        assert.match(response.headers['content-type'], /text\/event-stream/);
        assert.equal(response.text, SSE_BODY);
        const visitor = response.cookies.find((cookie) => cookie.startsWith('qs_visitor='));
        assert.match(visitor, /HttpOnly/);
        assert.match(visitor, /SameSite=Lax/);
        assert.equal(cookieValue(response.cookies, 'qs_chat_session'), SESSION_A);

        const [request] = ai.requests;
        assert.equal(request.url, '/chat/website');
        assert.equal(request.headers.authorization, `Bearer ${API_KEY}`);
        assert.deepEqual(request.body, {
            schema_version: '1.0',
            session_id: null,
            message: { text: 'Địa chỉ công ty?' },
        });
    });

    test('existing visitor and session cookies are reused', async () => {
        const visitor = '33333333-3333-4333-8333-333333333333';

        const response = await chat({ Cookie: `qs_visitor=${visitor}; qs_chat_session=${SESSION_A}` });

        assert.equal(response.status, 200);
        assert.equal(cookieValue(response.cookies, 'qs_visitor'), undefined);
        assert.equal(ai.requests[0].body.session_id, SESSION_A);
    });

    test('stale session is cleared and the chat retried once as a new conversation', async () => {
        ai.reply = (request, res) => (request.body.session_id
            ? json(404, { detail: { code: 'session_not_found', message: 'gone' } })(request, res)
            : sse(SESSION_B)(request, res));

        const response = await chat({ Cookie: `qs_chat_session=${SESSION_A}` });

        assert.equal(response.status, 200);
        assert.deepEqual(ai.requests.map((request) => request.body.session_id), [SESSION_A, null]);
        assert.equal(cookieValue(response.cookies.filter((c) => !c.includes('Max-Age=0')), 'qs_chat_session'), SESSION_B);
    });

    test('session_id is removed from the done event even when split across chunks', async () => {
        ai.reply = (request, res) => {
            res.writeHead(200, { 'Content-Type': 'text/event-stream', 'X-Session-ID': SESSION_A });
            res.write('event: delta\ndata: {"text":"A"}\n\nevent: done\ndata: {"request_id":"r1",');
            setTimeout(() => res.end(`"session_id":"${SESSION_A}"}\n\n`), 20);
        };

        const response = await chat();

        assert.equal(response.text, 'event: delta\ndata: {"text":"A"}\n\nevent: done\ndata: {"request_id":"r1"}\n\n');
        assert.ok(!response.text.includes(SESSION_A));
    });

    test('client context and UUID idempotency key are forwarded', async () => {
        const key = '44444444-4444-4444-8444-444444444444';

        await chat({ 'Idempotency-Key': key }, { message: { text: 'hi' }, client_context: { locale: 'vi' } });

        assert.equal(ai.requests[0].headers['idempotency-key'], key);
        assert.deepEqual(ai.requests[0].body.client_context, { locale: 'vi' });
    });

    test('foreign origin is rejected before calling AI', async () => {
        const response = await chat({ Origin: 'https://evil.example' });

        assert.equal(response.status, 403);
        assert.equal(JSON.parse(response.text).detail.code, 'origin_not_allowed');
        assert.equal(ai.requests.length, 0);
    });

    test('invalid JSON and missing text are rejected', async () => {
        const broken = await call('/api/chat', { method: 'POST', headers: { Origin: ORIGIN }, body: '{oops' });
        const empty = await chat({}, { message: { text: '   ' } });

        assert.equal(broken.status, 400);
        assert.equal(JSON.parse(broken.text).detail.code, 'invalid_json');
        assert.equal(empty.status, 400);
        assert.equal(ai.requests.length, 0);
    });

    test('service key rejection is hidden behind 502 and logged without the key', async () => {
        ai.reply = json(401, { detail: { code: 'invalid_service_key', message: 'bad key' } });

        const response = await chat();

        assert.equal(response.status, 502);
        assert.equal(JSON.parse(response.text).detail.code, 'chat_unavailable');
        assert.ok(logs.some((line) => line.includes('code=invalid_service_key')));
        assert.ok(!logs.join('\n').includes(API_KEY));
        assert.ok(!logs.join('\n').includes('Địa chỉ'));
    });

    test('AI validation and availability errors are relayed', async () => {
        ai.reply = json(503, { detail: { code: 'provider_not_configured', message: 'not configured' } });

        const response = await chat();

        assert.equal(response.status, 503);
        assert.equal(JSON.parse(response.text).detail.code, 'provider_not_configured');
    });

    test('unreachable AI service returns 502', async () => {
        const down = createWidgetServer({
            port: 0,
            aiServiceUrl: 'http://127.0.0.1:9',
            apiKey: API_KEY,
            allowedOrigins: new Set([ORIGIN]),
            cookieSecure: false,
            aiResponseTimeoutMs: 2000,
        }, { logger });
        const port = await listen(down);
        const saved = widgetPort;
        widgetPort = port;
        try {
            const response = await chat();
            assert.equal(response.status, 502);
            assert.equal(JSON.parse(response.text).detail.code, 'ai_service_unreachable');
        } finally {
            widgetPort = saved;
            down.close();
        }
    });
});

describe('GET /api/chat/history and POST /api/chat/reset', () => {
    test('history without session cookie is empty and does not call AI', async () => {
        const response = await call('/api/chat/history');

        assert.equal(response.status, 200);
        assert.deepEqual(JSON.parse(response.text), { messages: [] });
        assert.equal(ai.requests.length, 0);
    });

    test('history is proxied without exposing session_id', async () => {
        const messages = [{ id: 'h1', query_origin: 'hi', answer: 'chào' }];
        ai.reply = json(200, { session_id: SESSION_A, messages });

        const response = await call('/api/chat/history', { headers: { Cookie: `qs_chat_session=${SESSION_A}` } });

        assert.equal(ai.requests[0].url, `/chatbot/sessions/${SESSION_A}/history`);
        assert.equal(ai.requests[0].headers.authorization, `Bearer ${API_KEY}`);
        assert.deepEqual(JSON.parse(response.text), { messages });
    });

    test('history of a missing session clears the cookie', async () => {
        ai.reply = json(404, { detail: { code: 'session_not_found', message: 'gone' } });

        const response = await call('/api/chat/history', { headers: { Cookie: `qs_chat_session=${SESSION_A}` } });

        assert.deepEqual(JSON.parse(response.text), { messages: [] });
        assert.ok(response.cookies.some((cookie) => cookie.startsWith('qs_chat_session=;') && cookie.includes('Max-Age=0')));
    });

    test('reset clears the session cookie', async () => {
        const response = await call('/api/chat/reset', { method: 'POST', headers: { Origin: ORIGIN } });

        assert.equal(response.status, 204);
        assert.ok(response.cookies.some((cookie) => cookie.startsWith('qs_chat_session=;') && cookie.includes('Max-Age=0')));
    });

    test('unknown route is 404 and health is ok', async () => {
        assert.equal((await call('/api/unknown')).status, 404);
        assert.deepEqual(JSON.parse((await call('/health')).text), { status: 'ok' });
    });
});
