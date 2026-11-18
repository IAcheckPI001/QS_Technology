import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './errors.js';

vi.mock('./client.js', () => ({ api: { get: vi.fn() } }));
const { api } = await import('./client.js');
const { CONVERSATION_PAGE_SIZE, conversationParams, conversationsApi } = await import('./conversations.js');

describe('conversationsApi (B2: lọc và chia trang ở máy chủ)', () => {
  beforeEach(() => api.get.mockReset());

  it('listPage gửi bộ lọc, limit và cursor; trả items và next_cursor của máy chủ', async () => {
    api.get.mockResolvedValue({ conversations: [{ session_id: 's1' }], next_cursor: 'abc', total: null });
    const filters = { q: ' cam bien ', status: 'error', channel: 'crm', productModel: 'F86', from: '2026-11-12', to: '2026-11-18' };
    const page = await conversationsApi.listPage(filters, { cursor: 'prev' });

    expect(api.get).toHaveBeenCalledWith('/chatbot/conversations', expect.objectContaining({
      params: { q: 'cam bien', status: 'error', channel: 'crm', product_model: 'F86', from: '2026-11-12', to: '2026-11-18', limit: CONVERSATION_PAGE_SIZE, cursor: 'prev' },
    }));
    expect(page).toEqual({ items: [{ session_id: 's1' }], next_cursor: 'abc' });
  });

  it('bỏ tham số rỗng', () => {
    expect(conversationParams({ q: '  ', status: '', channel: '', productModel: '', from: '2026-11-12', to: '2026-11-18' }))
      .toEqual({ from: '2026-11-12', to: '2026-11-18' });
  });

  it('metrics: route chưa bật (404) thì trả null; lỗi khác ném tiếp', async () => {
    api.get.mockRejectedValueOnce(new ApiError({ status: 404, kind: 'not_found', code: 'not_found' }));
    expect(await conversationsApi.metrics({ from: '2026-11-12', to: '2026-11-18' })).toBeNull();
    expect(api.get).toHaveBeenCalledWith('/chatbot/conversations/metrics', expect.objectContaining({ params: { from: '2026-11-12', to: '2026-11-18' } }));

    api.get.mockRejectedValueOnce(new ApiError({ status: 503, kind: 'server' }));
    await expect(conversationsApi.metrics({})).rejects.toMatchObject({ kind: 'server' });
  });
});
