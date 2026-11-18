import { describe, expect, it } from 'vitest';
import { foldText, highlightParts, matchesAll, searchTokens } from './search.js';
import { activeRange, presetRange, quickRanges, rangeError, vnToday } from '../features/conversations/timeRange.js';

describe('tìm không dấu (giống máy chủ)', () => {
  it('bỏ dấu, kể cả đ/Đ', () => {
    expect(foldText('Đổi cảm biến báo lỗi ĐƯỜNG')).toBe('doi cam bien bao loi duong');
  });

  it('tách từ, bỏ từ dưới 2 ký tự, bỏ trùng, tối đa 8 từ', () => {
    expect(searchTokens(' Cảm  biến a lỗi cảm ')).toEqual(['cam', 'bien', 'loi']);
    expect(searchTokens('a1 a2 a3 a4 a5 a6 a7 a8 a9')).toHaveLength(8);
  });

  it('mọi từ phải có, không cần đúng thứ tự', () => {
    expect(matchesAll('F86 điều khiển được tối đa bao nhiêu trục?', 'truc dieu khien')).toBe(true);
    expect(matchesAll('F86 điều khiển', 'dieu khien F54')).toBe(false);
  });

  it('tô sáng giữ chữ gốc, gộp đoạn chồng nhau', () => {
    expect(highlightParts('Đổi cảm biến', 'cam bien')).toEqual([
      { text: 'Đổi ', hit: false },
      { text: 'cảm', hit: true },
      { text: ' ', hit: false },
      { text: 'biến', hit: true },
    ]);
    expect(highlightParts('Đường dây', 'duong')).toEqual([{ text: 'Đường', hit: true }, { text: ' dây', hit: false }]);
    expect(highlightParts('abc', '')).toEqual([{ text: 'abc', hit: false }]);
  });

  it('chữ dạng tổ hợp (NFD): tô cả dấu đi kèm', () => {
    const text = 'cả'.normalize('NFD') + 'm';
    const parts = highlightParts(text, 'cam');
    expect(parts).toEqual([{ text, hit: true }]);
  });
});

describe('khoảng thời gian (Q19, giờ Việt Nam)', () => {
  it('hôm nay theo UTC+7', () => {
    expect(vnToday(Date.parse('2026-11-17T17:30:00Z'))).toBe('2026-11-18');
    expect(vnToday(Date.parse('2026-11-17T16:30:00Z'))).toBe('2026-11-17');
  });

  it('các lựa chọn có sẵn', () => {
    expect(presetRange('7d', '2026-11-18')).toEqual({ from: '2026-11-12', to: '2026-11-18' });
    expect(presetRange('30d', '2026-11-18')).toEqual({ from: '2026-10-20', to: '2026-11-18' });
    expect(presetRange('month', '2026-11-18')).toEqual({ from: '2026-11-01', to: '2026-11-18' });
    const quick = Object.fromEntries(quickRanges('2026-11-18').map((item) => [item.label, [item.from, item.to]]));
    expect(quick['Tuần này']).toEqual(['2026-11-16', '2026-11-18']); // 18/11/2026 là thứ Tư
    expect(quick['Tháng trước']).toEqual(['2026-10-01', '2026-10-31']);
  });

  it('kiểm tra khoảng tuỳ chọn', () => {
    expect(rangeError('', '2026-11-18', '2026-11-18')).toMatch(/đủ/);
    expect(rangeError('2026-11-12', '2026-11-10', '2026-11-18')).toMatch(/trước/);
    expect(rangeError('2026-11-12', '2026-11-19', '2026-11-18')).toMatch(/sau hôm nay/);
    expect(rangeError('2025-01-01', '2026-11-18', '2026-11-18')).toMatch(/366/);
    expect(rangeError('2026-11-01', '2026-11-18', '2026-11-18')).toBeNull();
  });

  it('khoảng tuỳ chọn sai trên URL thì về mặc định 7 ngày', () => {
    expect(activeRange({ time: 'custom', from: '2026-11-20', to: '2026-11-21' }, '2026-11-18')).toMatchObject({ from: '2026-11-12', custom: false });
    expect(activeRange({ time: 'custom', from: '2026-11-01', to: '2026-11-02' }, '2026-11-18')).toMatchObject({ from: '2026-11-01', custom: true });
  });
});
