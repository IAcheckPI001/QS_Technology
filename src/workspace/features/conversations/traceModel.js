// Đọc trace (cây span, chỉ metadata) thành thứ màn Diễn biến cần (FRONTEND_REQUIREMENTS M3):
// thứ tự cây, nhãn tiếng Việt, span lỗi gốc, nhận diện chặn bằng action=block (không bằng status),
// gom tool_errors. Hàm thuần, không phụ thuộc React.

import { S } from '../../strings.vi.js';
import { toolErrorInfo, toolLabel } from './toolErrors.js';

const NEUTRAL = new Set(['deduplicated', 'cancelled', 'unfinished']);

/** Bước lỗi: khác ok và khác các trạng thái trung tính (gọi trùng, đã ngắt, chưa xong). */
export function isFailed(status) {
  return Boolean(status) && status !== 'ok' && !NEUTRAL.has(status);
}

export function spanStatusLabel(status) {
  if (S.trace.spanStatus[status]) return S.trace.spanStatus[status];
  const http = /^http_(\d{3})$/.exec(status || '');
  if (http) return S.trace.httpStatus(http[1]);
  // Span gốc lỗi mang mã SSE của lượt (analysis_error, agent_error…; thấy ở dữ liệu thật 17/11).
  if (/_error$/.test(status || '')) return S.trace.spanStatus.error;
  return status || '—';
}

/** Nhãn kết quả theo span: lỗi của span công cụ dùng nghĩa theo công cụ (toolErrors.js). */
export function spanResultLabel(span) {
  if (span.kind === 'tool' && span.name.startsWith('tool.') && isFailed(span.status) && !/^http_/.test(span.status)) {
    return toolErrorInfo(span.name.slice(5), span.status).short;
  }
  return spanStatusLabel(span.status);
}

/** Câu giải thích lỗi của span công cụ (null nếu không phải lỗi công cụ). */
export function spanErrorInfo(span) {
  if (span.kind !== 'tool' || !span.name.startsWith('tool.') || !isFailed(span.status)) return null;
  return toolErrorInfo(span.name.slice(5), span.status);
}

export function spanStatusTone(status) {
  if (status === 'ok') return 'success';
  if (NEUTRAL.has(status)) return 'neutral';
  return 'danger';
}

export function spanLabel(span) {
  const attrs = span.attributes || {};
  if (span.name.startsWith('http.')) {
    const target = attrs.dataset || attrs.table;
    return target ? `${S.trace.httpPrefix} · ${target}` : S.trace.httpPrefix;
  }
  const base = S.trace.spans[span.name];
  if (!base) return span.name; // span mới chưa có nhãn: hiện nguyên tên kỹ thuật
  if (span.name === 'llm.chat_tools' && attrs.step) return S.trace.step(base, attrs.step);
  return base;
}

/** Sắp span theo cây (cha trước con, anh em theo start_ms), kèm độ sâu. */
export function orderSpans(spans = []) {
  const ids = new Set(spans.map((span) => span.span_id));
  const children = new Map();
  const roots = [];
  for (const span of spans) {
    if (span.parent_id && ids.has(span.parent_id)) {
      if (!children.has(span.parent_id)) children.set(span.parent_id, []);
      children.get(span.parent_id).push(span);
    } else {
      roots.push(span);
    }
  }
  const byStart = (a, b) => (a.start_ms ?? 0) - (b.start_ms ?? 0);
  const out = [];
  const walk = (span, depth) => {
    out.push({ span, depth, hasFailedChild: false });
    const kids = (children.get(span.span_id) || []).sort(byStart);
    const row = out[out.length - 1];
    for (const kid of kids) {
      if (isFailed(kid.status)) row.hasFailedChild = true;
      walk(kid, depth + 1);
    }
  };
  roots.sort(byStart).forEach((root) => walk(root, 0));
  return out;
}

/** Nơi lỗi phát sinh: span lỗi không có span con nào lỗi (sớm nhất trước). */
export function rootErrorSpans(rows) {
  return rows.filter((row) => isFailed(row.span.status) && !row.hasFailedChild).map((row) => row.span);
}

function root(trace) {
  return (trace.spans || []).find((span) => !span.parent_id) || null;
}

/** Bước đang chạy lúc mất kết nối: span "cancelled" sâu nhất. */
function cancelledStep(rows) {
  const cancelled = rows.filter((row) => row.span.status === 'cancelled' && row.depth > 0);
  return cancelled.length ? cancelled[cancelled.length - 1].span : null;
}

function groupToolErrors(list = []) {
  const counts = new Map();
  for (const item of list) {
    const [tool, code] = String(item).split(':');
    const label = `${toolLabel(tool)}: ${toolErrorInfo(tool, code || 'unknown').text}`;
    counts.set(label, (counts.get(label) || 0) + 1);
  }
  return [...counts.entries()].map(([label, count]) => ({ label, count }));
}

/**
 * Loại lượt và nội dung hộp thông báo đầu trang.
 * kind: 'error' | 'blocked' | 'cancelled' | 'tool_warning' | 'ok'
 */
export function describeTrace(trace) {
  const rows = orderSpans(trace.spans);
  const rootSpan = root(trace);
  const attrs = rootSpan?.attributes || {};
  const summary = trace.summary || {};
  const security = (trace.spans || []).find((span) => span.name === 'stage.security');
  const securityAttrs = security?.attributes || {};

  if (trace.outcome === 'request_blocked' || attrs.flow === 'blocked' || securityAttrs.action === 'block') {
    const categories = [].concat(securityAttrs.categories || []);
    const groups = categories.map((category) => S.trace.category[category] || category).join(', ') || '—';
    const severity = S.trace.severity[securityAttrs.highest_severity] || securityAttrs.highest_severity || '';
    return { kind: 'blocked', rows, title: S.trace.blockedTitle, body: S.trace.blockedBody(groups, severity), focus: security || null };
  }
  if (trace.outcome === 'client_disconnected') {
    const step = cancelledStep(rows);
    return {
      kind: 'cancelled',
      rows,
      title: S.trace.cancelledTitle(step ? spanLabel(step) : ''),
      body: S.trace.cancelledBody(attrs.deltas),
      focus: step,
    };
  }
  if (trace.outcome && trace.outcome !== 'ok') {
    const origins = rootErrorSpans(rows);
    const origin = origins[0] || null;
    const step = origin ? stepName(rows, origin) : S.trace.spans['chat.request'];
    const code = origin?.attributes?.provider_error_code;
    const provider = code ? S.trace.provider[code] || S.trace.providerUnknown(code) : '';
    return { kind: 'error', rows, title: S.trace.failedAt(step), body: [provider, S.trace.failedBody].filter(Boolean).join(' '), focus: origin };
  }
  const failedTools = summary.failed_tool_calls || 0;
  if (failedTools > 0 || (attrs.tool_errors || []).length > 0) {
    return {
      kind: 'tool_warning',
      rows,
      title: S.trace.toolWarnTitle(failedTools || (attrs.tool_errors || []).length, summary.tool_calls || failedTools),
      body: S.trace.toolWarnBody,
      items: groupToolErrors(attrs.tool_errors),
      focus: rootErrorSpans(rows)[0] || null,
    };
  }
  return { kind: 'ok', rows, focus: null };
}

/** Tên bước để báo lỗi: span lỗi gốc là lời gọi AI thì nói theo stage cha ("Phân tích câu hỏi"). */
function stepName(rows, span) {
  if (span.name.startsWith('llm.') || span.name.startsWith('http.') || span.name === 'embedding') {
    const parent = rows.find((row) => row.span.span_id === span.parent_id)?.span;
    if (parent && parent.name.startsWith('stage.')) return spanLabel(parent);
  }
  return spanLabel(span);
}
