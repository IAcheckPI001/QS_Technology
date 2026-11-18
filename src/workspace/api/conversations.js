// Hội thoại: các endpoint đã có trên backend (routers/workspace.py, api_guidelines.md).
// Backend chưa phân trang (B2, FRONTEND_REQUIREMENTS mục 19): `listPage` tải danh sách đầy đủ một lần
// cho mỗi bộ lọc rồi cắt trang ở trình duyệt, trả cùng dạng { items, next_cursor, total } như API
// sau B2 để màn hình không phải đổi. Khi có B2 chỉ cần gửi `limit`/`cursor` lên server.
// Bật VITE_WORKSPACE_FIXTURES=1 (hoặc có "conversations") khi chạy dev để dùng dữ liệu giả.

import { fixturesFor } from '../config.js';
import { api } from './client.js';

export const CONVERSATION_PAGE_SIZE = 25;
export const TURN_PAGE_SIZE = 20;

const session = (id) => `/chatbot/sessions/${encodeURIComponent(id)}`;

const real = {
  list: ({ search, status } = {}, options) => api.get('/chatbot/conversations', { ...options, params: { search, status } }),
  history: (sessionId, options) => api.get(`${session(sessionId)}/history`, options),
  retrieval: (sessionId, options) => api.get(`${session(sessionId)}/retrieval`, options),
  // B5: nguồn câu trả lời của đúng một lượt (FRONTEND_REQUIREMENTS 19.15).
  retrievalForTurn: (sessionId, historyId, options) =>
    api.get(`${session(sessionId)}/retrieval`, { ...options, params: { history_id: historyId } }),
  trace: (sessionId, historyId, options) => api.get(`${session(sessionId)}/trace`, { ...options, params: { history_id: historyId } }),
};

// Dữ liệu giả nạp động và chỉ khi chạy dev: bản build production thay `import.meta.env.DEV` bằng false
// nên không có chunk dữ liệu giả.
const loadFixtures = import.meta.env.DEV && fixturesFor('conversations') ? () => import('./fixtures/conversations.js') : null;
const pick = (name) => (...args) =>
  loadFixtures ? loadFixtures().then((module) => module.fixtureConversations[name](...args)) : real[name](...args);
const source = {
  list: pick('list'),
  history: pick('history'),
  retrieval: pick('retrieval'),
  retrievalForTurn: pick('retrievalForTurn'),
  trace: pick('trace'),
};

// Danh sách đầy đủ của bộ lọc gần nhất, dùng lại khi "Tải thêm" (cursor = vị trí bắt đầu).
let cached = { key: null, data: null };

async function listPage({ search = '', status = '' } = {}, { cursor = null, signal } = {}) {
  const key = JSON.stringify([search, status]);
  if (!cursor || cached.key !== key || !cached.data) {
    const data = await source.list({ search: search || undefined, status: status || undefined }, { signal });
    cached = { key, data };
  }
  const all = cached.data.conversations || [];
  const start = cursor ? Number(cursor) || 0 : 0;
  const end = start + CONVERSATION_PAGE_SIZE;
  return { items: all.slice(start, end), next_cursor: end < all.length ? String(end) : null, total: all.length };
}

export const conversationsApi = {
  listPage,
  history: (sessionId, options) => source.history(sessionId, options),
  retrieval: (sessionId, options) => source.retrieval(sessionId, options),
  retrievalForTurn: (sessionId, historyId, options) => source.retrievalForTurn(sessionId, historyId, options),
  trace: (sessionId, historyId, options) => source.trace(sessionId, historyId, options),
};

/** Chỉ dùng trong test: bỏ danh sách đã nhớ. */
export function resetConversationCache() {
  cached = { key: null, data: null };
}
