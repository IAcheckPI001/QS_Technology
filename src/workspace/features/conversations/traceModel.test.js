import { describe, expect, it } from 'vitest';
import { describeTrace, isFailed, orderSpans, rootErrorSpans, spanLabel, spanStatusLabel } from './traceModel.js';
import { askedAt, formatDuration, formatDurationShort } from '../../utils/format.js';

const sp = (span_id, parent_id, name, start_ms, status = 'ok', attributes = {}) => ({ span_id, parent_id, name, kind: 'stage', start_ms, duration_ms: 10, status, attributes });

describe('đọc trace', () => {
  it('sắp theo cây: cha trước con, anh em theo thời gian bắt đầu', () => {
    const rows = orderSpans([sp('3', '1', 'history.write', 50), sp('1', null, 'chat.request', 0), sp('2', '1', 'stage.analysis', 10), sp('4', '2', 'llm.chat_json', 12)]);
    expect(rows.map((row) => [row.span.span_id, row.depth])).toEqual([['1', 0], ['2', 1], ['4', 2], ['3', 1]]);
  });

  it('gọi trùng, đã ngắt, chưa xong không tính là lỗi', () => {
    expect(['ok', 'deduplicated', 'cancelled', 'unfinished'].map(isFailed)).toEqual([false, false, false, false]);
    expect(['error', 'tool_call_limit', 'http_404'].map(isFailed)).toEqual([true, true, true]);
    expect(spanStatusLabel('http_503')).toBe('Trả HTTP 503');
    expect(spanStatusLabel('analysis_error')).toBe('Lỗi');
  });

  it('nhãn tiếng Việt; span mới chưa có nhãn hiện tên kỹ thuật', () => {
    expect(spanLabel(sp('1', null, 'llm.chat_tools', 0, 'ok', { step: 3 }))).toBe('AI chọn bước tiếp theo · bước 3');
    expect(spanLabel(sp('1', null, 'http.crm_report', 0, 'ok', { dataset: 'customers' }))).toBe('Gọi API CRM · customers');
    expect(spanLabel(sp('1', null, 'stage.new_thing', 0))).toBe('stage.new_thing');
  });

  it('lượt lỗi: báo bước lỗi gốc theo stage cha và mã lỗi nhà cung cấp', () => {
    const trace = {
      outcome: 'analysis_error',
      spans: [
        sp('1', null, 'chat.request', 0, 'error'),
        sp('2', '1', 'stage.analysis', 10, 'error'),
        sp('3', '2', 'llm.chat_json', 11, 'error', { provider_error_code: 'credit_balance_exhausted' }),
      ],
    };
    const info = describeTrace(trace);
    expect(info.kind).toBe('error');
    expect(rootErrorSpans(info.rows).map((span) => span.span_id)).toEqual(['3']);
    expect(info.title).toBe('Lượt này thất bại ở bước “Phân tích câu hỏi”.');
    expect(info.body).toMatch(/hết credit/);

    // Dữ liệu thật 18/11: khóa API hết hạn (401).
    trace.spans[2].attributes = { provider_error_code: 'expired_secret_key', http_status: 401 };
    expect(describeTrace(trace).body).toMatch(/Khóa API OpenAI của hệ thống đã hết hạn/);
  });

  it('bị chặn nhận bằng action=block, không bằng status của span', () => {
    const trace = {
      outcome: 'request_blocked',
      spans: [sp('1', null, 'chat.request', 0, 'ok', { flow: 'blocked' }), sp('2', '1', 'stage.security', 1, 'ok', { action: 'block', categories: ['ignore_instructions'], highest_severity: 'high' })],
    };
    const info = describeTrace(trace);
    expect(info.kind).toBe('blocked');
    expect(info.body).toContain('yêu cầu bỏ qua chỉ dẫn');
    expect(info.body).toContain('cao');
    expect(info.focus.span_id).toBe('2');
  });

  it('đã ngắt: nêu bước đang chạy và số đoạn đã gửi', () => {
    const trace = {
      outcome: 'client_disconnected',
      spans: [sp('1', null, 'chat.request', 0, 'cancelled', { deltas: 14 }), sp('2', '1', 'stage.compose', 5, 'cancelled'), sp('3', '2', 'llm.stream_chat', 6, 'cancelled')],
    };
    const info = describeTrace(trace);
    expect(info.kind).toBe('cancelled');
    expect(info.title).toContain('AI viết câu trả lời');
    expect(info.body).toContain('14 đoạn');
  });

  it('hoàn tất nhưng công cụ lỗi: cảnh báo và gom nguyên nhân', () => {
    const trace = {
      outcome: 'ok',
      summary: { tool_calls: 3, failed_tool_calls: 2 },
      spans: [sp('1', null, 'chat.request', 0, 'ok', { tool_errors: ['crm_query:crm_unavailable', 'crm_query:crm_unavailable'] })],
    };
    const info = describeTrace(trace);
    expect(info.kind).toBe('tool_warning');
    expect(info.title).toBe('Đã trả lời, nhưng 2 / 3 lần dùng công cụ không thành công.');
    expect(info.items).toEqual([
      { label: 'Truy vấn dữ liệu CRM: Không lấy được dữ liệu từ CRM: CRM không phản hồi, quá thời gian hoặc trả lỗi.', count: 2 },
    ]);
  });

  it('hoàn tất không lỗi thì không có hộp thông báo', () => {
    expect(describeTrace({ outcome: 'ok', summary: {}, spans: [sp('1', null, 'chat.request', 0)] }).kind).toBe('ok');
  });
});

describe('định dạng', () => {
  it('giờ hỏi = created_at − latency_ms; thiếu latency thì null', () => {
    expect(askedAt({ created_at: '2026-11-18T01:00:10.000Z', latency_ms: 4000 }).toISOString()).toBe('2026-11-18T01:00:06.000Z');
    expect(askedAt({ created_at: '2026-11-18T01:00:10.000Z', latency_ms: null })).toBeNull();
  });

  it('thời lượng', () => {
    expect(formatDuration(124)).toBe('124 ms');
    expect(formatDuration(4800)).toBe('4,8 giây');
    expect(formatDurationShort(2350)).toBe('2,35 s');
  });
});
