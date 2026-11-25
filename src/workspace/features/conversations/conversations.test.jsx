import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ApiError } from '../../api/errors.js';
import ConversationDetailPage from './ConversationDetailPage.jsx';
import ConversationsPage from './ConversationsPage.jsx';
import TracePage from './TracePage.jsx';

vi.mock('../../api/conversations.js', () => ({
  CONVERSATION_PAGE_SIZE: 25,
  TURN_PAGE_SIZE: 20,
  conversationsApi: { listPage: vi.fn(), metrics: vi.fn(), history: vi.fn(), retrieval: vi.fn(), retrievalForTurn: vi.fn(), trace: vi.fn() },
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

const METRICS = { conversation_count: 3, handoff_count: 1, question_count: 12, cost_usd: 0.01, cost_vnd: 260 };

describe('Lịch sử hội thoại', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-11-18T05:00:00Z')); // 12:00 giờ Việt Nam
    conversationsApi.metrics.mockReset().mockResolvedValue(METRICS);
    conversationsApi.listPage.mockReset();
  });
  afterEach(() => vi.useRealTimers());

  it('hiện trang đầu, 4 ô số liệu, cột số câu hỏi và chi phí; "Tải thêm" nối trang kế', async () => {
    conversationsApi.listPage
      .mockResolvedValueOnce({ items: [conv(1, { product_models: ['F54'], ticket_id: 'TK-1048', question_count: 7, cost_vnd: 12.5 }), conv(2, { status: 'error' })], next_cursor: 'c2' })
      .mockResolvedValueOnce({ items: [conv(3)], next_cursor: null });
    renderAt('/conversations');

    const table = await screen.findByRole('table');
    expect(within(table).getByRole('link', { name: 'Câu hỏi 1' }).getAttribute('href')).toBe('/conversations/s1');
    expect(within(table).getByText('#TK-1048')).toBeTruthy();
    expect(within(table).getByText('Lỗi')).toBeTruthy();
    expect(within(table).getByText('7')).toBeTruthy();
    const metrics = screen.getByRole('region', { name: 'Chỉ số' });
    expect(await within(metrics).findByText('12')).toBeTruthy();
    expect(within(metrics).getAllByText(/trong 7 ngày qua/)).toHaveLength(4);
    expect(screen.getByText('Đang hiển thị 2 / 3 hội thoại')).toBeTruthy();
    // Mặc định lọc 7 ngày qua theo giờ Việt Nam (Q19).
    expect(conversationsApi.listPage).toHaveBeenCalledWith(
      { q: '', status: '', channel: '', productModel: '', from: '2026-11-12', to: '2026-11-18' },
      expect.objectContaining({ cursor: null }),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Tải thêm 25 hội thoại' }));
    expect(await within(table).findByRole('link', { name: 'Câu hỏi 3' })).toBeTruthy();
    expect(screen.getByText('Đã hiển thị hết')).toBeTruthy();
    expect(conversationsApi.listPage).toHaveBeenLastCalledWith(expect.anything(), expect.objectContaining({ cursor: 'c2' }));
  });

  it('dòng khớp ở lượt khác: ghi "Khớp ở lượt N", tô từ khớp không dấu, link mở đúng lượt', async () => {
    conversationsApi.listPage.mockResolvedValue({
      items: [conv(1, { last_query: 'Cảm ơn', match: { history_id: 'h3', turn_number: 3, query: 'Đổi cảm biến báo lỗi' } })],
      next_cursor: null,
    });
    renderAt('/conversations?q=cam%20bien');

    const table = await screen.findByRole('table');
    expect(within(table).getByText('Khớp ở lượt 3:', { exact: false })).toBeTruthy();
    const marks = [...table.querySelectorAll('mark')].map((mark) => mark.textContent);
    expect(marks).toEqual(['Cảm', 'cảm', 'biến']);
    expect(within(table).getByRole('link', { name: 'Cảm ơn' }).getAttribute('href')).toBe('/conversations/s1?turn=h3&q=cam+bien');
    conversationsApi.history.mockResolvedValue({ session_id: 's1', messages: [turn(3)] });
    conversationsApi.retrieval.mockResolvedValue(null);
    fireEvent.click(within(table).getByRole('link', { name: 'Cảm ơn' }));
    expect(screen.getByTestId('where').textContent).toBe('/conversations/s1?turn=h3&q=cam+bien');
  });

  it('lọc trạng thái ghi lên URL và tải lại từ đầu; kênh CRM khoá "Chuyển nhân viên"; không khớp thì có "Xoá bộ lọc"', async () => {
    conversationsApi.listPage.mockResolvedValue({ items: [], next_cursor: null });
    renderAt('/conversations');
    await screen.findByText('Chưa có hội thoại nào');

    fireEvent.change(screen.getByLabelText('Trạng thái'), { target: { value: 'error' } });
    expect(screen.getByTestId('where').textContent).toBe('/conversations?status=error');
    await waitFor(() => expect(conversationsApi.listPage).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'error' }), expect.objectContaining({ cursor: null })));
    expect(conversationsApi.metrics).toHaveBeenLastCalledWith(expect.objectContaining({ status: 'error' }), expect.anything());

    fireEvent.change(screen.getByLabelText('Kênh'), { target: { value: 'crm' } });
    const handoff = within(screen.getByLabelText('Trạng thái')).getByRole('option', { name: /Chuyển nhân viên/ });
    expect(handoff.disabled).toBe(true);

    fireEvent.click(await screen.findByRole('button', { name: 'Xoá bộ lọc' }));
    expect(screen.getByTestId('where').textContent).toBe('/conversations');
  });

  it('khoảng tuỳ chọn: kiểm tra ngày, áp dụng thì lọc và hiện thẻ; bỏ thẻ thì về 7 ngày qua', async () => {
    conversationsApi.listPage.mockResolvedValue({ items: [conv(1)], next_cursor: null });
    renderAt('/conversations');
    await screen.findByRole('table');

    fireEvent.change(screen.getByLabelText('Thời gian'), { target: { value: 'custom' } });
    const panel = screen.getByRole('dialog', { name: 'Chọn khoảng thời gian' });
    fireEvent.change(within(panel).getByLabelText('Từ ngày'), { target: { value: '2026-11-10' } });
    fireEvent.change(within(panel).getByLabelText('Đến ngày'), { target: { value: '2026-11-19' } });
    expect(within(panel).getByRole('alert').textContent).toBe('Không chọn ngày sau hôm nay.');
    expect(within(panel).getByRole('button', { name: 'Áp dụng' }).disabled).toBe(true);

    fireEvent.change(within(panel).getByLabelText('Đến ngày'), { target: { value: '2026-11-11' } });
    fireEvent.click(within(panel).getByRole('button', { name: 'Áp dụng' }));
    expect(screen.getByTestId('where').textContent).toBe('/conversations?time=custom&from=2026-11-10&to=2026-11-11');
    expect(screen.getByText('Từ 10/11/2026 đến 11/11/2026 · 2 ngày')).toBeTruthy();
    await waitFor(() => expect(conversationsApi.listPage).toHaveBeenLastCalledWith(expect.objectContaining({ from: '2026-11-10', to: '2026-11-11' }), expect.anything()));

    fireEvent.click(screen.getByRole('button', { name: 'Bỏ lọc thời gian' }));
    expect(screen.getByTestId('where').textContent).toBe('/conversations');
  });

  it('đang lọc "Chuyển nhân viên" mà chọn kênh CRM thì bỏ luôn trạng thái trên URL', async () => {
    conversationsApi.listPage.mockResolvedValue({ items: [conv(1)], next_cursor: null });
    renderAt('/conversations?status=handoff');
    await screen.findByRole('table');
    fireEvent.change(screen.getByLabelText('Kênh'), { target: { value: 'crm' } });
    expect(screen.getByTestId('where').textContent).toBe('/conversations?channel=crm');
    fireEvent.change(screen.getByLabelText('Kênh'), { target: { value: 'website' } });
    expect(screen.getByTestId('where').textContent).toBe('/conversations?channel=website');
  });

  it('bảng chọn khoảng: bấm ra ngoài là huỷ; thẻ khoảng có "Sửa" mở lại với ngày đang lọc', async () => {
    conversationsApi.listPage.mockResolvedValue({ items: [conv(1)], next_cursor: null });
    const { container } = renderAt('/conversations?time=custom&from=2026-11-01&to=2026-11-05');
    await screen.findByRole('table');
    expect(within(screen.getByLabelText('Thời gian', { selector: 'select' })).getByRole('option', { name: 'Tuỳ chọn: 01/11 – 05/11' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Sửa' }));
    const panel = screen.getByRole('dialog', { name: 'Chọn khoảng thời gian' });
    expect(within(panel).getByLabelText('Từ ngày').value).toBe('2026-11-01');
    fireEvent.mouseDown(container.querySelector('[class*="rangeBackdrop"]'));
    expect(screen.queryByRole('dialog', { name: 'Chọn khoảng thời gian' })).toBeNull();
    expect(screen.getByTestId('where').textContent).toBe('/conversations?time=custom&from=2026-11-01&to=2026-11-05');
  });

  it('điện thoại: ô tìm + chip; sheet chỉnh nháp, "Xem n hội thoại" mới áp dụng; chip có × bỏ từng bộ lọc', async () => {
    const original = window.matchMedia;
    window.matchMedia = (query) => ({ matches: query.includes('720'), media: query, addEventListener() {}, removeEventListener() {} });
    try {
      conversationsApi.listPage.mockResolvedValue({ items: [conv(1)], next_cursor: null });
      renderAt('/conversations');
      await screen.findByRole('group', { name: 'Bộ lọc đang dùng' });
      expect(screen.queryByLabelText('Kênh')).toBeNull();
      const chips = screen.getByRole('group', { name: 'Bộ lọc đang dùng' });
      expect(within(chips).getByRole('button', { name: '7 ngày qua' })).toBeTruthy();

      fireEvent.click(within(chips).getByRole('button', { name: 'Bộ lọc' }));
      const sheet = screen.getByRole('dialog', { name: 'Bộ lọc' });
      fireEvent.click(within(sheet).getByRole('button', { name: 'CRM' }));
      expect(within(sheet).getByRole('button', { name: 'Chuyển nhân viên' }).disabled).toBe(true);
      fireEvent.click(within(sheet).getByRole('button', { name: 'Lỗi' }));
      // Chưa áp dụng: URL chưa đổi.
      expect(screen.getByTestId('where').textContent).toBe('/conversations');
      const apply = await within(sheet).findByRole('button', { name: 'Xem 3 hội thoại' });
      fireEvent.click(apply);
      expect(screen.getByTestId('where').textContent).toBe('/conversations?channel=crm&status=error');
      expect(within(chips).getByRole('button', { name: 'Bộ lọc · 2' })).toBeTruthy();

      fireEvent.click(within(chips).getByRole('button', { name: 'Bỏ lọc CRM' }));
      expect(screen.getByTestId('where').textContent).toBe('/conversations?status=error');
    } finally {
      window.matchMedia = original;
    }
  });

  it('máy chủ chưa bật route số liệu: ẩn các ô số liệu, không có "/ y"', async () => {
    conversationsApi.metrics.mockResolvedValue(null);
    conversationsApi.listPage.mockResolvedValue({ items: [conv(1)], next_cursor: null });
    renderAt('/conversations');
    await screen.findByRole('table');
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Chỉ số' })).toBeNull());
    expect(screen.getByText('Đang hiển thị 1 hội thoại')).toBeTruthy();
  });

  it('lỗi tải thì báo và cho thử lại', async () => {
    conversationsApi.listPage.mockRejectedValueOnce(new ApiError({ status: 503, kind: 'server' })).mockResolvedValueOnce({ items: [conv(1)], next_cursor: null });
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
    expect(await within(first).findByText(/Tài liệu đã dùng \(1\)/)).toBeTruthy();
    const second = screen.getByRole('article', { name: 'Lượt 2' });
    expect(within(second).queryByText(/Tài liệu đã dùng/)).toBeNull();
    expect(within(second).getByText('Chatbot · không có câu trả lời')).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Tài liệu chatbot đã dùng · lượt 1' })).toBeTruthy();
    expect(screen.getByText('Cấu hình')).toBeTruthy();

    fireEvent.click(within(second).getByRole('button', { name: 'Chi tiết kỹ thuật' }));
    expect(within(second).getByRole('link', { name: 'Xem diễn biến xử lý' }).getAttribute('href')).toBe('/conversations/s1/turns/h2/trace');
  });

  it('mở từ kết quả tìm kiếm (?turn=): hiện cả lượt khớp cũ hơn 20 lượt mới nhất, đánh dấu và tô từ khoá', async () => {
    conversationsApi.history.mockResolvedValue({ session_id: 's1', messages: Array.from({ length: 30 }, (_, i) => turn(i + 1, i === 2 ? { query_origin: 'Đổi cảm biến home' } : {})) });
    conversationsApi.retrieval.mockResolvedValue(null);
    render(
      <MemoryRouter initialEntries={[{ pathname: '/conversations/s1', search: '?turn=h3&q=cam%20bien', state: { from: '?q=cam%20bien' } }]}>
        <Routes>
          <Route path="/conversations/:sessionId" element={<ConversationDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    const focused = await screen.findByRole('article', { name: 'Lượt 3' });
    expect(screen.getByRole('link', { name: 'Lịch sử hội thoại' }).getAttribute('href')).toBe('/conversations?q=cam%20bien');
    expect(focused.getAttribute('data-focus')).toBe('true');
    expect([...focused.querySelectorAll('mark')].map((mark) => mark.textContent)).toEqual(['cảm', 'biến']);
    // 28 lượt (3…30) đang hiện, còn 2 lượt cũ hơn.
    expect(screen.getAllByRole('article')).toHaveLength(28);
    expect(screen.getByRole('button', { name: 'Tải 2 lượt cũ hơn' })).toBeTruthy();
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

    const label = async (no) => srcButton(await screen.findByRole('article', { name: `Lượt ${no}` })).textContent;
    expect(await label(1)).toBe('Tài liệu đã dùng (2)');
    expect(await label(2)).toBe('Dữ liệu CRM (3 lần gọi) · có lỗi');
    expect(await label(3)).toBe('Không có nguồn');
    expect(await label(4)).toBe('Không có nguồn');
    expect(await label(5)).toBe('Không tìm thấy tài liệu');
    expect(await label(6)).toBe('Không tra cứu · đang xem');

    expect(await screen.findByRole('heading', { name: 'Nguồn câu trả lời · lượt 6' })).toBeTruthy();
    expect(await screen.findByText('Chatbot trả lời trực tiếp, không cần tra cứu')).toBeTruthy();
    expect(conversationsApi.retrievalForTurn).toHaveBeenCalledWith('s1', 'h6', expect.anything());

    fireEvent.click(srcButton(screen.getByRole('article', { name: 'Lượt 2' })));
    expect(await screen.findByRole('heading', { name: 'Nguồn câu trả lời · lượt 2' })).toBeTruthy();
    expect(await screen.findByText('Đọc cấu trúc dữ liệu CRM')).toBeTruthy();
    expect(screen.getByText('2 lần: 1 thành công, 1 lỗi')).toBeTruthy();
    expect(screen.getByText('CRM không có bảng dữ liệu AI muốn đọc.')).toBeTruthy();
    expect(screen.getByText('Câu trả lời có số liệu từ CRM.')).toBeTruthy();

    fireEvent.click(srcButton(screen.getByRole('article', { name: 'Lượt 1' })));
    expect(await screen.findByText('Được trích dẫn [S1]')).toBeTruthy();
    expect(screen.getByText('f54_operation_v02 · 2.3 Homing')).toBeTruthy();
  });

  it('câu trả lời hiện Markdown (tiêu đề, bảng), không còn cú pháp thô', async () => {
    conversationsApi.history.mockResolvedValue({
      session_id: 's1',
      messages: [turn(1, { answer: '### Cách sử dụng bộ điều khiển F86\n\n| Thông số | F86 |\n|---|---|\n| Số trục | 6 |', sources: src('direct', 'not_applicable') })],
    });
    conversationsApi.retrievalForTurn.mockResolvedValue({ history_id: 'h1', turn_status: 'completed', retrieval_status: 'not_applicable', sources: src('direct', 'not_applicable'), chunks: [] });
    renderAt('/conversations/s1');
    const article = await screen.findByRole('article', { name: 'Lượt 1' });
    expect(within(article).getByRole('heading', { level: 3, name: 'Cách sử dụng bộ điều khiển F86' })).toBeTruthy();
    expect(within(article).getByRole('cell', { name: '6' })).toBeTruthy();
    expect(article.textContent).not.toContain('###');
  });

  it('bấm huy hiệu [S2] ở lượt cũ: chọn lượt đó, mở và đánh dấu đoạn S2; gợi ý tên tài liệu và trang', async () => {
    conversationsApi.history.mockResolvedValue({
      session_id: 's1',
      messages: [
        turn(1, { answer: 'Homing dùng G28 [S2].', sources: src('documents', 'ok', { chunk_count: 2 }) }),
        turn(2, { sources: src('direct', 'not_applicable') }),
      ],
    });
    const chunk = (rank, sid, extra = {}) => ({ rank, score: 0.03, content: `Nội dung ${sid}`, scopes: [], source_id: sid, chunk_id: `c${rank}`, doc_title: 'F54 Operation Guide', ...extra });
    conversationsApi.retrievalForTurn.mockImplementation(async (sid, hid) => ({
      h1: { history_id: 'h1', turn_status: 'completed', retrieval_status: 'ok', sources: src('documents', 'ok', { chunk_count: 2 }), chunks: [chunk(1, 'S1'), chunk(2, 'S2', { page_start: 41, page_end: 42 })] },
      h2: { history_id: 'h2', turn_status: 'completed', retrieval_status: 'not_applicable', sources: src('direct', 'not_applicable'), chunks: [] },
    })[hid]);
    renderAt('/conversations/s1');
    expect(await screen.findByRole('heading', { name: 'Nguồn câu trả lời · lượt 2' })).toBeTruthy();

    const badge = within(screen.getByRole('article', { name: 'Lượt 1' })).getByRole('button', { name: /^Nguồn S2/ });
    expect(badge.textContent).toBe('2');
    fireEvent.click(badge);
    expect(await screen.findByRole('heading', { name: 'Nguồn câu trả lời · lượt 1' })).toBeTruthy();
    const target = await screen.findByRole('article', { name: '#2 · S2' });
    await waitFor(() => expect(within(target).getByRole('button', { name: 'Thu gọn' }).getAttribute('aria-expanded')).toBe('true'));
    expect(target.className).toMatch(/chunkFocus/);
    expect(within(screen.getByRole('article', { name: '#1 · S1' })).getByRole('button', { name: 'Xem đầy đủ nội dung' })).toBeTruthy();
    expect(within(target).getByText('F54 Operation Guide · tr. 41–42')).toBeTruthy();
    const after = within(screen.getByRole('article', { name: 'Lượt 1' })).getByRole('button', { name: /^Nguồn S2/ });
    expect(after.getAttribute('title')).toBe('F54 Operation Guide · tr. 41–42');
  });

  it('lượt lỗi: khung nguồn nói nguyên nhân từ diễn biến; lượt không lưu diễn biến thì nói không rõ', async () => {
    conversationsApi.history.mockResolvedValue({
      session_id: 's1',
      messages: [
        turn(1, { status: 'error', answer: null, has_trace: true, sources: src('direct', 'not_applicable') }),
        turn(2, { status: 'error', answer: null, has_trace: false, sources: src('direct', 'not_applicable') }),
      ],
    });
    conversationsApi.retrievalForTurn.mockImplementation(async (sid, hid) => ({ history_id: hid, turn_status: 'error', retrieval_status: 'not_applicable', sources: src('direct', 'not_applicable'), chunks: [] }));
    conversationsApi.trace.mockReset().mockResolvedValue({
      session_id: 's1', history_id: 'h1', channel: 'website', outcome: 'answer_error', duration_ms: 900, created_at: '2026-11-18T01:00:00Z', summary: {},
      spans: [
        { span_id: '1', parent_id: null, name: 'chat.request', kind: 'server', start_ms: 0, duration_ms: 900, status: 'error', attributes: {} },
        { span_id: '2', parent_id: '1', name: 'stage.analysis', kind: 'stage', start_ms: 5, duration_ms: 800, status: 'error', attributes: {} },
        { span_id: '3', parent_id: '2', name: 'llm.analysis', kind: 'client', start_ms: 6, duration_ms: 700, status: 'error', attributes: { provider_error_code: 'insufficient_quota' } },
      ],
    });
    renderAt('/conversations/s1');

    expect(await screen.findByText('Lượt này bị lỗi nên không có nguồn')).toBeTruthy();
    expect(screen.getByText(/không lưu diễn biến xử lý/)).toBeTruthy();
    expect(conversationsApi.trace).not.toHaveBeenCalled();

    fireEvent.click(srcButton(screen.getByRole('article', { name: 'Lượt 1' })));
    expect(await screen.findByText('Lượt này thất bại ở bước “Phân tích câu hỏi”.')).toBeTruthy();
    expect(screen.getByText(/hết hạn mức \(hết credit\)/)).toBeTruthy();
    expect(screen.getByText('insufficient_quota')).toBeTruthy();
    expect(conversationsApi.trace).toHaveBeenCalledWith('s1', 'h1', expect.anything());
  });
});

describe('Nguồn câu trả lời · đợt 2 (WU-17)', () => {
  const src = (answer_source, retrieval_status, extra = {}) => ({ answer_source, retrieval_status, chunk_count: 0, tools: [], has_tool_errors: false, ...extra });

  it('độ khớp thang 10 từ similarity, ảnh của đoạn; lượt cũ không có similarity thì ẩn điểm', async () => {
    conversationsApi.history.mockResolvedValue({ session_id: 's1', messages: [turn(1, { answer: 'Đấu dây [S1].', sources: src('documents', 'ok', { chunk_count: 2 }) })] });
    conversationsApi.retrievalForTurn.mockResolvedValue({
      history_id: 'h1', turn_status: 'completed', retrieval_status: 'ok', sources: src('documents', 'ok', { chunk_count: 2 }),
      chunks: [
        { rank: 1, score: 0.031, similarity: 0.742, content: 'Cổng CN1', scopes: [], source_id: 'S1', chunk_id: 'c1', section_title: 'Port', images: [{ url: 'https://p.supabase.co/sign/p7.png?token=t', page: 7, printed_page: 7 }, { url: 'javascript:alert(1)', page: 8 }] },
        { rank: 2, score: 0.02, content: 'Lượt cũ', scopes: [], chunk_id: 'c2' },
      ],
    });
    renderAt('/conversations/s1');
    const first = await screen.findByRole('article', { name: '#1 · S1' });
    expect(within(first).getByText('7,4/10')).toBeTruthy();
    expect(screen.getAllByText('7,4/10')).toHaveLength(2); // ô "Độ khớp cao nhất" + thẻ đoạn
    const [img] = within(first).getAllByRole('img');
    expect(img.getAttribute('src')).toBe('https://p.supabase.co/sign/p7.png?token=t');
    expect(within(first).getAllByRole('img')).toHaveLength(1); // URL không phải https bị bỏ
    const old = screen.getByRole('article', { name: '#2' });
    expect(within(old).queryByText(/\/10/)).toBeNull();
  });

  it('lượt lỗi có mã lưu sẵn: nhãn "Lỗi ở bước …", khung nguồn nói nguyên nhân không cần trace', async () => {
    const error = { stage: 'analysis', code: 'analysis_failed', provider_code: 'invalid_api_key', http_status: 401 };
    conversationsApi.history.mockResolvedValue({ session_id: 's1', messages: [turn(1, { status: 'error', answer: null, has_trace: false, error, sources: src('direct', 'not_applicable') })] });
    conversationsApi.retrievalForTurn.mockResolvedValue({ history_id: 'h1', turn_status: 'error', retrieval_status: 'not_applicable', sources: src('direct', 'not_applicable'), chunks: [], error });
    conversationsApi.trace.mockReset();
    renderAt('/conversations/s1');
    expect(srcButton(await screen.findByRole('article', { name: 'Lượt 1' })).textContent).toMatch(/^Lỗi ở bước “Phân tích câu hỏi”/);
    expect(await screen.findByText('Lượt này thất bại ở bước “Phân tích câu hỏi”.')).toBeTruthy();
    expect(screen.getByText(/không hợp lệ/)).toBeTruthy();
    expect(screen.getByText('invalid_api_key')).toBeTruthy();
    expect(conversationsApi.trace).not.toHaveBeenCalled();
  });
});

/** Nút nhãn nguồn dưới lượt (không phải huy hiệu trích dẫn trong câu trả lời). */
function srcButton(article) {
  return within(article).getAllByRole('button').find((button) => !(button.getAttribute('aria-label') || '').startsWith('Nguồn '));
}

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
