const DEFAULT_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173';

const positiveInt = (value, fallback, name) => {
    if (value === undefined || value === '') return fallback;
    const parsed = Number(value);
    if (!Number.isInteger(parsed) || parsed <= 0) throw new Error(`${name} must be a positive integer`);
    return parsed;
};

// Đọc cấu hình một lần lúc khởi động; thiếu service key thì dừng ngay thay vì trả 502 lúc chạy.
export function loadConfig(env = process.env) {
    const apiKey = (env.CHATBOT_API_KEY ?? '').trim();
    if (!apiKey) throw new Error('CHATBOT_API_KEY is required (service key kênh website)');

    return {
        port: positiveInt(env.PORT, 8787, 'PORT'),
        aiServiceUrl: (env.AI_SERVICE_URL || 'http://localhost:8000').replace(/\/+$/, ''),
        apiKey,
        allowedOrigins: new Set(
            (env.ALLOWED_ORIGINS || DEFAULT_ORIGINS).split(',').map((origin) => origin.trim()).filter(Boolean),
        ),
        cookieSecure: env.COOKIE_SECURE === 'true',
        aiResponseTimeoutMs: positiveInt(env.AI_RESPONSE_TIMEOUT_MS, 30000, 'AI_RESPONSE_TIMEOUT_MS'),
    };
}
