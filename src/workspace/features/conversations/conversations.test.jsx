import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ApiError } from '../../api/errors.js';
import ConversationDetailPage from './ConversationDetailPage.jsx';
import ConversationsPage from './ConversationsPage.jsx';
import TracePage from './TracePage.jsx';

vi.mock('../../api/conversations.js', () => ({
  CONVERSATION_PAGE_SIZE: 25,
  TURN_PAGE_SIZE: 20,
  conversationsApi: { listPage: vi.fn(), history: vi.fn(), retrieval: vi.fn(), retrievalForTurn: vi.fn(), trace: vi.fn() },
}));
const { conversationsApi } = await import('../../api/conversations.js');

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname}{location.search}</p>;
}

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/conversations" element={<><ConversationsPage /><Where /></>} />
        <Route path="/conversations/:sessionId" element={<><ConversationDetailPage /><Where /></>} />
        <Route path="/conversations/:sessionId/turns/:historyId/trace" element={<TracePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

const conv = (i, extra = {}) => ({
  session_id: `s${i}`, last_query: `Câu hỏi ${i}`, channel: i % 2 ? 'crm' : 'website', status: 'completed',
  created_at: '2026-11-18T01:00:00Z', updated_date: '2026-11-18T01:05:00Z', product_models: [], ticket_id: null, ...extra,
});

const turn = (i, extra = {}) => ({
  id: `h${i}`, session_id: 's1', query_origin: `Hỏi ${i}`, answer: `Đáp ${i}`, status: 'completed', channel: 'crm',
  created_at: new Date(Date.UTC(2026, 10, 18, 1, i)).toISOString(), updated_date: '2026-11-18T01:00:00Z',
  latency_ms: 4000, total_tokens: 100, cost_usd: 0.0001, model: 'gpt-4.1-mini', ...extra,
});

describe('Lịch sử hội thoại', () => {
  it('hiện trang đầu, "Tải thêm" nối trang kế, hết thì báo đã hiển thị hết', async () => {
    conversationsApi.listPage
      .mockResolvedValueOnce({ items: [conv(1, { product_models: ['F54'], ticket_id: 'TK-1048' }), conv(2, { status: 'error' })], next_cursor: '2', total: 3 })
      .mockResolvedValueOnce({ items: [conv(3)], next_cursor: null, total: 3 });
    renderAt('/conversations');

    const table = await screen.findByRole('table');
    expect(within(table).getByRole('link', { name: 'Câu hỏi 1' }).getAttribute('href')).toBe('/conversations/s1');
    expect(within(table).getByText('#TK-1048')).toBeTruthy();
    expect(within(table).getByText('Lỗi')).toBeTruthy();
    expect(screen.getByText('Đang hiển thị 2 / 3 hội thoại')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Tải thêm 25 hội thoại' }));
    expect(await within(table).findByRole('link', { name: 'Câu hỏi 3' })).toBeTruthy();
    expect(screen.getByText('Đã hiển thị hết')).toBeTruthy();
    expect(conversationsApi.listPage).toHaveBeenLastCalledWith({ search: '', status: '' }, expect.objectContaining({ cursor: '2' }));
  });

  it('lọc trạng thái ghi lên URL và tải lại từ đầu; không khớp thì có "Xoá bộ lọc"', async () => {
    conversationsApi.listPage.mockResolvedValue({ items: [], next_cursor: null, total: 0 });
    renderAt('/conversations');
    await screen.findByText('Chưa có hội thoại nào');

    fireEvent.change(screen.getByLabelText('Trạng thái'), { target: { value: 'error' } });
    expect(screen.getByTestId('where').textContent).toBe('/conversations?status=error');
    await waitFor(() => expect(conversationsApi.listPage).toHaveBeenLastCalledWith({ search: '', status: 'error' }, expect.objectContaining({ cursor: null })));
    fireEvent.click(await screen.findByRole('button', { name: 'Xoá bộ lọc' }));
    expect(screen.getByTestId('where').textContent).toBe('/conversations');
  });

  it('lỗi tải thì báo và cho thử lại', async () => {
    conversationsApi.listPage.mockRejectedValueOnce(new ApiError({ status: 503, kind: 'server' })).mockResolvedValueOnce({ items: [conv(1)], next_cursor: null, total: 1 });
    renderAt('/conversations');
    fireEvent.click(await screen.findByRole('button', { name: 'Thử lại' }));
    expect(await screen.findByRole('table')).toBeTruthy();
  });
});

describe('Chi tiết hội thoại', () => {
  it('giờ hỏi tính từ latency; tài liệu chỉ có ở lượt máy chủ trả về', async () => {
    conversationsApi.history.mockResolvedValue({ session_id: 's1', messages: [turn(1), turn(2, { status: 'error', answer: null })] });
    conversationsApi.retrieval.mockResolvedValue({ history_id: 'h1', retrieval_status: 'ok', latency_ms: 120, chunks: [{ rank: 1, score: 0.9, content: 'Nội dung đoạn', scopes: ['configuration'] }] });
    renderAt('/conversations/s1');

    const first = await screen.findByRole('article', { name: 'Lượt 1' });
    // Tiêu đề = câu hỏi cuối, khớp danh sách (WU-10).
    expect(screen.getByRole('heading', { level: 1 }).textContent).toBe('Hỏi 2');
    // created_at 01:01 UTC − 4 giây = 08:00:56 giờ Việt Nam
    expect(within(first).getByText('Khách hỏi · 08:00')).toBeTruthy();
    expect(within(first).getByText(/Tài liệu đã dùng \(1\)/)).toBeTruthy();
    const second = screen.getByRole('article', { name: 'Lượt 2' });
    expect(within(second).queryByText(/Tài liệu đã dùng/)).toBeNull();
    expect(within(second).getByText('Chatbot · không có câu trả lời')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Tài liệu chatbot đã dùng · lượt 1' })).toBeTruthy();
    expect(screen.getByText('Cấu hình')).toBeTruthy();

    fireEvent.click(within(second).getByRole('button', { name: 'Chi tiết kỹ thuật' }));
    expect(within(second).getByRole('link', { name: 'Xem diễn biến xử lý' }).getAttribute('href')).toBe('/conversations/s1/turns/h2/trace');
  });

  it('hội thoại dài: hiện 20 lượt mới nhất, "Tải lượt cũ hơn" thêm phần còn lại', async () => {
    conversationsApi.history.mockResolvedValue({ session_id: 's1', messages: Array.from({ length: 23 }, (_, i) => turn(i + 1)) });
    conversationsApi.retrieval.mockRejectedValue(new ApiError({ status: 404, kind: 'not_found', code: 'retrieval_not_found' }));
    renderAt('/conversations/s1');

    expect(await screen.findByRole('article', { name: 'Lượt 23' })).toBeTruthy();
    expect(screen.queryByRole('article', { name: 'Lượt 3' })).toBeNull();
    expect(await screen.findByText('Hội thoại chưa có lượt nào dùng tài liệu')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Tải 3 lượt cũ hơn' }));
    expect(screen.getByRole('article', { name: 'Lượt 1' })).toBeTruthy();
    expect(screen.getByRole('note').textContent).toMatch(/Đầu hội thoại/);
  });

  it('chi tiết kỹ thuật: usage thật hiện token vào/ra, số lần gọi AI, chi phí VND; lượt cũ ghi rõ ước tính', async () => {
    conversationsApi.history.mockResolvedValue({
      session_id: 's1',
      messages: [
        turn(1, { input_tokens: 31168, output_tokens: 259, cost_usd: 0.0129, cost_vnd: 335.4, usage: { source: 'trace', llm_calls: 6, unpriced_models: [] } }),
        turn(2, { total_tokens: 54, cost_usd: 0.000026, cost_vnd: 0.68, usage: { source: 'estimate' } }),
      ],
    });
    conversationsApi.retrieval.mockResolvedValue(null);
    renderAt('/conversations/s1');

    const real = await screen.findByRole('article', { name: 'Lượt 1' });
    fireEvent.click(within(real).getByRole('button', { name: 'Chi tiết kỹ thuật' }));
    expect(within(real).getByText('31.168 / 259')).toBeTruthy();
    expect(within(real).getByText('335 đ')).toBeTruthy();
    expect(within(real).getByText('6')).toBeTruthy();

    const old = screen.getByRole('article', { name: 'Lượt 2' });
    fireEvent.click(within(old).getByRole('button', { name: 'Chi tiết kỹ thuật' }));
    expect(within(old).getByText('< 1 đ')).toBeTruthy();
    expect(within(old).getByText(/thấp hơn thực tế/)).toBeTruthy();
  });

  it('không có hội thoại thì báo không tìm thấy', async () => {
    conversationsApi.history.mockRejectedValue(new ApiError({ status: 404, kind: 'not_found', code: 'session_not_found' }));
    conversationsApi.retrieval.mockResolvedValue(null);
    renderAt('/conversations/nope');
    expect(await screen.findByText('Không tìm thấy hội thoại')).toBeTruthy();
  });
});

describe('Nguồn câu trả lời theo lượt (B5, Q28)', () => {
  const src = (answer_source, retrieval_status, extra = {}) => ({ answer_source, retrieval_status, chunk_count: 0, tools: [], has_tool_errors: false, ...extra });
  const crmTools = [{ name: 'crm_schema', calls: 2, failed: 1, errors: { crm_query_invalid: 1 } }, { name: 'crm_query', calls: 1, failed: 0, errors: {} }];

  it('nhãn dưới mỗi lượt theo loại nguồn; mặc định xem lượt mới nhất; bấm lượt khác thì tải nguồn lượt đó', async () => {
    conversationsApi.history.mockResolvedValue({
      session_id: 's1',
      messages: [
        turn(1, { answer: 'Đáp [S1]', sources: src('documents', 'ok', { chunk_count: 2 }) }),
        turn(2, { sources: src('crm_data', 'not_applicable', { tools: crmTools, has_tool_errors: true }) }),
        turn(3, { status: 'blocked', sources: src('none', null) }),
        turn(4, { status: 'error', answer: null, sources: src('direct', 'not_applicable') }),
        turn(5, { sources: src('documents', 'no_hits') }),
        turn(6, { sources: src('direct', 'not_applicable') }),
      ],
    });
    conversationsApi.retrievalForTurn.mockImplementation(async (sid, hid) => ({
      h1: { history_id: 'h1', turn_status: 'completed', retrieval_status: 'ok', sources: src('documents', 'ok', { chunk_count: 1 }), chunks: [{ rank: 1, score: 0.9, content: 'Đoạn', scopes: [], source_id: 'S1', doc_id: 'f54_operation_v02', section_path: ['2.3 Homing'] }] },
      h2: { history_id: 'h2', turn_status: 'completed', retrieval_status: 'not_applicable', sources: src('crm_data', 'not_applicable', { tools: crmTools, has_tool_errors: true }), chunks: [] },
      h6: { history_id: 'h6', turn_status: 'completed', retrieval_status: 'not_applicable', sources: src('direct', 'not_applicable'), chunks: [] },
    })[hid]);
    renderAt('/conversations/s1');

    const label = async (no) => within(await screen.findByRole('article', { name: `Lượt ${no}` })).getAllByRole('button')[0].textContent;
    expect(await label(1)).toBe('Tài liệu đã dùng (2)');
    expect(await label(2)).toBe('Dữ liệu CRM (3 lần gọi) · có lỗi');
    expect(await label(3)).toBe('Không có nguồn');
    expect(await label(4)).toBe('Không có nguồn');
    expect(await label(5)).toBe('Không tìm thấy tài liệu');
    expect(await label(6)).toBe('Không tra cứu · đang xem');

    expect(await screen.findByRole('heading', { name: 'Nguồn câu trả lời · lượt 6' })).toBeTruthy();
    expect(await screen.findByText('Chatbot trả lời trực tiếp, không cần tra cứu')).toBeTruthy();
    expect(conversationsApi.retrievalForTurn).toHaveBeenCalledWith('s1', 'h6', expect.anything());

    fireEvent.click(within(screen.getByRole('article', { name: 'Lượt 2' })).getAllByRole('button')[0]);
    expect(await screen.findByRole('heading', { name: 'Nguồn câu trả lời · lượt 2' })).toBeTruthy();
    expect(await screen.findByText('Đọc cấu trúc dữ liệu CRM')).toBeTruthy();
    expect(screen.getByText('2 lần: 1 thành công, 1 lỗi')).toBeTruthy();
    expect(screen.getByText('CRM không có bảng dữ liệu AI muốn đọc.')).toBeTruthy();
    expect(screen.getByText('Câu trả lời có số liệu từ CRM.')).toBeTruthy();

    fireEvent.click(within(screen.getByRole('article', { name: 'Lượt 1' })).getAllByRole('button')[0]);
    expect(await screen.findByText('Được trích dẫn [S1]')).toBeTruthy();
    expect(screen.getByText('f54_operation_v02 · 2.3 Homing')).toBeTruthy();
  });
});

describe('Diễn biến xử lý', () => {
  it('không có trace là trạng thái rỗng, không phải lỗi', async () => {
    conversationsApi.trace.mockRejectedValue(new ApiError({ status: 404, kind: 'not_found', code: 'trace_not_found' }));
    renderAt('/conversations/s1/turns/h1/trace');
    expect(await screen.findByText('Lượt này không có diễn biến xử lý')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('lượt lỗi: hộp lỗi, bước lỗi được chọn sẵn, lọc chỉ bước lỗi', async () => {
    conversationsApi.trace.mockResolvedValue({
      session_id: 's1', history_id: 'h1', channel: 'website', outcome: 'analysis_error', duration_ms: 500, created_at: '2026-11-18T01:00:00Z',
      summary: { llm_calls: 1, error_spans: 2, root_error_spans: 1 },
      spans: [
        { span_id: '1', parent_id: null, name: 'chat.request', kind: 'server', start_ms: 0, duration_ms: 500, status: 'error', attributes: { flow: 'pipeline' } },
        { span_id: '2', parent_id: '1', name: 'stage.security', kind: 'stage', start_ms: 5, duration_ms: 1, status: 'ok', attributes: {} },
        { span_id: '3', parent_id: '1', name: 'stage.analysis', kind: 'stage', start_ms: 10, duration_ms: 480, status: 'error', attributes: { error_type: 'Timeout' } },
      ],
    });
    renderAt('/conversations/s1/turns/h1/trace');

    expect((await screen.findByRole('alert')).textContent).toContain('Lượt này thất bại ở bước “Phân tích câu hỏi”.');
    expect(screen.getByRole('heading', { name: 'Diễn biến xử lý · lượt lỗi' })).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Phân tích câu hỏi · Lỗi' })).toBeTruthy();
    expect(screen.getByRole('button', { name: /Kiểm tra an toàn nội dung/ })).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Chỉ bước lỗi'));
    expect(screen.queryByRole('button', { name: /Kiểm tra an toàn nội dung/ })).toBeNull();
  });
});
