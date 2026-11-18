// Hội thoại: các endpoint của backend (routers/workspace.py, api_guidelines.md).
// B2 (FRONTEND_REQUIREMENTS 19.4–19.5): máy chủ lọc trên toàn bộ dữ liệu và chia trang theo cursor; số
// liệu theo cùng bộ lọc ở /metrics (chỉ có khi bật WORKSPACE_CONVERSATION_API_ENABLED, không có thì
// `metrics` trả null và màn ẩn các ô số liệu).
// Bật VITE_WORKSPACE_FIXTURES=1 (hoặc có "conversations") khi chạy dev để dùng dữ liệu giả.

import { fixturesFor } from '../config.js';
import { api } from './client.js';

export const CONVERSATION_PAGE_SIZE = 25;
export const TURN_PAGE_SIZE = 20;

const session = (id) => `/chatbot/sessions/${encodeURIComponent(id)}`;

const real = {
  list: (params, options) => api.get('/chatbot/conversations', { ...options, params }),
  metrics: (params, options) => api.get('/chatbot/conversations/metrics', { ...options, params }),
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
const source = Object.fromEntries(Object.keys(real).map((name) => [name, pick(name)]));

/**
 * Bộ lọc của màn → tham số query của máy chủ (bỏ giá trị rỗng).
 * filters: { q, status, channel, productModel, from, to }
 */
export function conversationParams({ q, status, channel, productModel, from, to } = {}) {
  const params = { q: q?.trim() || undefined, status, channel, product_model: productModel, from, to };
  return Object.fromEntries(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ''));
}

async function listPage(filters, { cursor = null, signal } = {}) {
  const data = await source.list(
    { ...conversationParams(filters), limit: CONVERSATION_PAGE_SIZE, ...(cursor ? { cursor } : {}) },
    { signal },
  );
  return { items: data.conversations || [], next_cursor: data.next_cursor || null };
}

async function metrics(filters, { signal } = {}) {
  try {
    return await source.metrics(conversationParams(filters), { signal });
  } catch (error) {
    if (error?.kind === 'not_found') return null; // máy chủ chưa bật route số liệu
    throw error;
  }
}

export const conversationsApi = {
  listPage,
  metrics,
  history: (sessionId, options) => source.history(sessionId, options),
  retrieval: (sessionId, options) => source.retrieval(sessionId, options),
  retrievalForTurn: (sessionId, historyId, options) => source.retrievalForTurn(sessionId, historyId, options),
  trace: (sessionId, historyId, options) => source.trace(sessionId, historyId, options),
};
