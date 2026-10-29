export class AiServiceUnreachable extends Error {
    constructor(cause) {
        super('AI service is unreachable', { cause });
        this.name = 'AiServiceUnreachable';
    }
}

// Client gọi dịch vụ AI bằng service key. Timeout chỉ áp cho tới khi nhận header:
// sau đó stream SSE chạy bao lâu cũng được, chỉ dừng khi trình duyệt ngắt.
export function createAiClient(config, fetchImpl = fetch) {
    async function request(path, { method = 'GET', headers = {}, body, signal }) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(new Error('AI response timeout')), config.aiResponseTimeoutMs);
        const onAbort = () => controller.abort(signal.reason);
        signal?.addEventListener('abort', onAbort, { once: true });
        try {
            return await fetchImpl(`${config.aiServiceUrl}${path}`, {
                method,
                headers: {
                    Authorization: `Bearer ${config.apiKey}`,
                    ...(body ? { 'Content-Type': 'application/json' } : {}),
                    ...headers,
                },
                body: body ? JSON.stringify(body) : undefined,
                signal: controller.signal,
            });
        } catch (error) {
            if (signal?.aborted) throw error; // trình duyệt đã ngắt, không phải lỗi dịch vụ AI
            throw new AiServiceUnreachable(error);
        } finally {
            clearTimeout(timer);
            signal?.removeEventListener('abort', onAbort);
        }
    }

    return {
        chatWebsite({ sessionId, message, clientContext, idempotencyKey, signal }) {
            return request('/chat/website', {
                method: 'POST',
                headers: {
                    Accept: 'text/event-stream',
                    ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {}),
                },
                body: {
                    schema_version: '1.0',
                    session_id: sessionId,
                    message,
                    ...(clientContext ? { client_context: clientContext } : {}),
                },
                signal,
            });
        },

        history(sessionId, { signal } = {}) {
            return request(`/chatbot/sessions/${encodeURIComponent(sessionId)}/history`, { signal });
        },
    };
}
