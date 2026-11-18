// Hội thoại: các endpoint đã có trên backend (routers/workspace.py). Hiện chưa phân trang và chỉ lọc
// `search`, `status` theo lượt mới nhất; phân trang/lọc kênh/thời gian/model chờ B2, tài liệu theo
// từng lượt chờ B5 (FRONTEND_REQUIREMENTS.md Q26, mục 11).

import { api } from './client.js';

export const conversationsApi = {
  list: ({ search, status } = {}, options) => api.get('/chatbot/conversations', { ...options, params: { search, status } }),
  history: (sessionId, options) => api.get(`/chatbot/sessions/${encodeURIComponent(sessionId)}/history`, options),
  retrieval: (sessionId, options) => api.get(`/chatbot/sessions/${encodeURIComponent(sessionId)}/retrieval`, options),
  trace: (sessionId, historyId, options) =>
    api.get(`/chatbot/sessions/${encodeURIComponent(sessionId)}/trace`, { ...options, params: { history_id: historyId } }),
};
