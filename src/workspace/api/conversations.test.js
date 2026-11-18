import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('./client.js', () => ({ api: { get: vi.fn() } }));
const { api } = await import('./client.js');
const { CONVERSATION_PAGE_SIZE, conversationsApi, resetConversationCache } = await import('./conversations.js');

const rows = (n) => Array.from({ length: n }, (_, i) => ({ session_id: `s${i}` }));

describe('listPage (cắt trang ở trình duyệt khi chưa có B2)', () => {
  beforeEach(() => resetConversationCache());

  it('trang đầu 25 dòng, "Tải thêm" dùng lại danh sách đã tải, không gọi lại API', async () => {
    api.get.mockResolvedValue({ conversations: rows(30) });
    const first = await conversationsApi.listPage({ search: 'f54', status: 'error' });
    expect(api.get).toHaveBeenCalledWith('/chatbot/conversations', expect.objectContaining({ params: { search: 'f54', status: 'error' } }));
    expect(first.items).toHaveLength(CONVERSATION_PAGE_SIZE);
    expect(first).toMatchObject({ next_cursor: '25', total: 30 });

    const second = await conversationsApi.listPage({ search: 'f54', status: 'error' }, { cursor: first.next_cursor });
    expect(api.get).toHaveBeenCalledTimes(1);
    expect(second.items.map((row) => row.session_id)).toEqual(['s25', 's26', 's27', 's28', 's29']);
    expect(second.next_cursor).toBeNull();
  });

  it('bộ lọc rỗng không gửi tham số; đổi bộ lọc thì tải lại', async () => {
    api.get.mockResolvedValue({ conversations: rows(2) });
    await conversationsApi.listPage({ search: '', status: '' });
    expect(api.get).toHaveBeenLastCalledWith('/chatbot/conversations', expect.objectContaining({ params: { search: undefined, status: undefined } }));
    await conversationsApi.listPage({ search: 'x', status: '' }, { cursor: '25' });
    expect(api.get).toHaveBeenCalledTimes(2);
  });
});
