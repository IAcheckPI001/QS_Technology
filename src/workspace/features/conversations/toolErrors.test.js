import { describe, expect, it } from 'vitest';
import { analyzeTools, toolErrorInfo } from './toolErrors.js';

const step = (name, status, kind = 'tool') => ({ step: 1, kind, name, status });

describe('nghĩa lỗi công cụ', () => {
  it('cùng mã khác nghĩa theo công cụ', () => {
    expect(toolErrorInfo('crm_schema', 'crm_query_invalid').text).toBe('CRM không có bảng dữ liệu AI muốn đọc.');
    expect(toolErrorInfo('crm_query', 'crm_query_invalid').text).toBe('CRM từ chối câu truy vấn AI dựng.');
    expect(toolErrorInfo('crm_query', 'tool_invalid_args').text).toMatch(/AI dựng câu truy vấn sai/);
    expect(toolErrorInfo('crm_query', 'ma_la_chua_biet')).toMatchObject({ code: 'ma_la_chua_biet', short: 'Lỗi' });
  });
});

describe('kết luận lượt CRM', () => {
  it('ví dụ 1: truy vấn sai một lần rồi tự sửa → có số liệu', () => {
    const { rows, verdict } = analyzeTools([
      step('auto', 'ok', 'llm'),
      step('crm_schema', 'ok'),
      step('crm_schema', 'ok'),
      step('crm_query', 'tool_invalid_args'),
      step('crm_query', 'ok'),
      step('crm_query', 'ok'),
    ]);
    expect(verdict).toMatchObject({ tone: 'success', title: 'Câu trả lời có số liệu từ CRM.', detail: 'AI gặp lỗi 1 lần rồi tự sửa.' });
    expect(rows.map((row) => [row.label, row.result])).toEqual([
      ['Đọc cấu trúc dữ liệu CRM', '2 lần, đều thành công'],
      ['Truy vấn dữ liệu CRM', '3 lần: 2 thành công, 1 lỗi đã tự sửa'],
    ]);
    expect(rows[1].reasons[0]).toMatchObject({ code: 'tool_invalid_args', count: 1 });
  });

  it('ví dụ 2: truy vấn CRM không thành công lần nào → có thể thiếu số liệu', () => {
    const { rows, verdict } = analyzeTools([
      step('crm_schema', 'crm_query_invalid'),
      step('crm_schema', 'deduplicated'),
      step('crm_schema', 'crm_query_invalid'),
      step('crm_schema', 'tool_call_limit'),
      step('crm_schema', 'tool_call_limit'),
      step('crm_query', 'crm_unavailable'),
    ]);
    expect(verdict.tone).toBe('warning');
    expect(verdict.title).toMatch(/Không lấy được số liệu từ CRM/);
    // Lần "gọi trùng" dùng lại kết quả lỗi trước đó: không phải thành công.
    expect(rows[0].result).toBe('5 lần: 4 lỗi, 1 gọi trùng');
    expect(rows[0].reasons.map((r) => [r.text, r.count])).toEqual([
      ['CRM không có bảng dữ liệu AI muốn đọc.', 2],
      ['AI gọi công cụ này quá số lần cho phép trong một câu hỏi, hệ thống dừng lại.', 2],
    ]);
    expect(rows[1].result).toBe('1 lần, lỗi');
  });

  it('không có agent_steps thì đếm theo sources.tools, không kết luận tự sửa', () => {
    const { rows, verdict, ordered } = analyzeTools([], {
      tools: [{ name: 'crm_query', calls: 3, failed: 1, errors: { tool_invalid_args: 1 } }],
    });
    expect(ordered).toBe(false);
    expect(rows[0].result).toBe('3 lần: 2 thành công, 1 lỗi');
    expect(verdict.tone).toBe('success');
    expect(verdict.detail).toBe('');
  });

  it('chỉ đọc cấu trúc, không truy vấn và không lỗi → trung tính', () => {
    expect(analyzeTools([step('crm_schema', 'ok')]).verdict.tone).toBe('neutral');
  });
});
