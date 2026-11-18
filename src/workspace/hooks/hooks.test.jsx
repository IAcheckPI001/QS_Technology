import { describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { useCursorList } from './useCursorList.js';
import { filtersToParams, parseFilters } from './useUrlFilters.js';

function pages(map) {
  return vi.fn(async ({ cursor }) => map[cursor ?? 'first']);
}

describe('useCursorList', () => {
  it('tải trang đầu, Tải thêm nối trang kế, hết thì done', async () => {
    const fetchPage = pages({
      first: { items: [1, 2], next_cursor: 'c2', total: 3 },
      c2: { items: [3], next_cursor: null },
    });
    const { result } = renderHook(() => useCursorList(fetchPage, 'k'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current).toMatchObject({ items: [1, 2], total: 3, done: false });

    act(() => result.current.loadMore());
    await waitFor(() => expect(result.current.done).toBe(true));
    expect(result.current.items).toEqual([1, 2, 3]);
  });

  it('bấm Tải thêm liên tiếp chỉ gửi một request', async () => {
    const fetchPage = pages({ first: { items: [1], next_cursor: 'c2' }, c2: { items: [2], next_cursor: 'c3' } });
    const { result } = renderHook(() => useCursorList(fetchPage, 'k'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => {
      result.current.loadMore();
      result.current.loadMore();
    });
    await waitFor(() => expect(result.current.loadingMore).toBe(false));
    expect(fetchPage).toHaveBeenCalledTimes(2);
  });

  it('đổi bộ lọc thì bỏ trang cũ và tải lại từ đầu', async () => {
    const fetchPage = vi.fn(async () => ({ items: ['x'], next_cursor: null }));
    const { result, rerender } = renderHook(({ key }) => useCursorList(fetchPage, key), { initialProps: { key: 'a' } });
    await waitFor(() => expect(result.current.loading).toBe(false));
    rerender({ key: 'b' });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetchPage).toHaveBeenCalledTimes(2);
    expect(fetchPage.mock.calls[1][0].cursor).toBeNull();
  });

  it('lỗi khi tải thêm giữ dữ liệu đã có', async () => {
    const fetchPage = vi.fn(async ({ cursor }) => {
      if (cursor) throw Object.assign(new Error('x'), { kind: 'network' });
      return { items: [1], next_cursor: 'c2' };
    });
    const { result } = renderHook(() => useCursorList(fetchPage, 'k'));
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.loadMore());
    await waitFor(() => expect(result.current.error).not.toBeNull());
    expect(result.current.items).toEqual([1]);
  });
});

describe('bộ lọc trên URL', () => {
  const defaults = { channel: 'all', time: '7d', q: '' };

  it('chỉ ghi giá trị khác mặc định', () => {
    expect(filtersToParams({ channel: 'crm', time: '7d', q: '' }, defaults).toString()).toBe('channel=crm');
  });

  it('đọc lại, thiếu thì lấy mặc định', () => {
    expect(parseFilters(new URLSearchParams('q=M1920'), defaults)).toEqual({ channel: 'all', time: '7d', q: 'M1920' });
  });
});
