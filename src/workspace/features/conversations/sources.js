// Loại nguồn câu trả lời của một lượt (FRONTEND_REQUIREMENTS 19.14, Q28) từ `sources` do backend B5 trả
// (answer_source, retrieval_status, chunk_count, tools) kết hợp trạng thái lượt. Hàm thuần.

import { S } from '../../strings.vi.js';

// docs | crm | both | direct | nohits | rerr | none
export function sourceKind(sources, turnStatus) {
  if (!sources) return null;
  const { answer_source: source, retrieval_status: status, chunk_count: chunks = 0 } = sources;
  // Lượt lỗi, bị chặn hoặc ngắt trước khi tra cứu/gọi công cụ: không có nguồn.
  if (source === 'none' || (source === 'direct' && turnStatus && turnStatus !== 'completed')) return 'none';
  if (source === 'direct') return 'direct';
  if (source === 'crm_data') return 'crm';
  if (source === 'documents_and_crm') return 'both';
  if (chunks > 0) return 'docs';
  if (status === 'no_hits') return 'nohits';
  if (status === 'error' || status === 'partial_error') return 'rerr';
  return 'none';
}

export function crmCalls(sources) {
  return (sources?.tools || []).reduce((sum, tool) => sum + (tool.calls || 0), 0);
}

/** Nhãn dưới lượt ở khung trái. */
export function sourceLabel(kind, sources) {
  const L = S.conv.src;
  switch (kind) {
    case 'docs':
      return L.docs(sources.chunk_count);
    case 'crm':
      return L.crm(crmCalls(sources), sources.has_tool_errors);
    case 'both':
      return L.both(sources.chunk_count, crmCalls(sources));
    default:
      return L[kind] || L.none;
  }
}

export function sourceTone(kind) {
  return { nohits: 'warning', rerr: 'danger', none: 'muted', direct: 'muted' }[kind] || 'brand';
}

/** Câu lý do khi lượt không có nguồn, theo trạng thái lượt. */
export function noneReason(turnStatus) {
  return S.conv.src.reason[turnStatus] || S.conv.src.reason.completed;
}

/** Mã nguồn (S1, S2…) được câu trả lời trích dẫn. */
export function citedSources(answer) {
  return new Set((String(answer || '').match(/\[S\d+\]/g) || []).map((tag) => tag.slice(1, -1)));
}
