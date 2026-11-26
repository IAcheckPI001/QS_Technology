// Tài liệu & chunk (B6 phần đọc): các endpoint /workspace/documents của backend (documents/router.py,
// api_guidelines.md). Chỉ có khi bật WORKSPACE_DOCUMENTS_API_ENABLED; tắt thì backend trả 404 → màn báo chưa bật.

import { API_BASE } from '../config.js';
import { api } from './client.js';

export const CHUNK_PAGE_SIZE = 20;

const doc = (docId) => `/workspace/documents/${encodeURIComponent(docId)}`;

/** Tham số lọc đoạn → query (bỏ giá trị rỗng). filters: { tab, q, section } */
export function chunkParams({ tab = 'all', q = '', section = [] } = {}) {
  const params = {};
  if (tab === 'pending') params.status = 'draft';
  if (tab === 'approved') params.status = 'approved';
  if (tab === 'images') params.has_images = true;
  if (q.trim()) params.q = q.trim();
  if (section.length) params.section = section;
  return params;
}

export const documentsApi = {
  tree: (options) => api.get('/workspace/documents', options),
  detail: (docId, options) => api.get(doc(docId), options),
  outline: (docId, options) => api.get(`${doc(docId)}/outline`, options),
  chunks: (docId, filters, { offset = 0, signal } = {}) =>
    api.get(`${doc(docId)}/chunks`, { signal, params: { ...chunkParams(filters), offset, limit: CHUNK_PAGE_SIZE } }),
  /** Link mở PDF: backend chuyển hướng tới link CRM mới ký (không lưu URL ký ở trình duyệt). */
  pdfUrl: (docId, mode = 'view') => `${API_BASE}${doc(docId)}/pdf?mode=${mode}`,
};
