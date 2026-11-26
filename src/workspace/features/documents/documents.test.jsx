import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ApiError } from '../../api/errors.js';
import { chunkParams } from '../../api/documents.js';
import DocumentsPage from './DocumentsPage.jsx';

vi.mock('../../api/documents.js', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    documentsApi: { tree: vi.fn(), detail: vi.fn(), outline: vi.fn(), chunks: vi.fn(), pdfUrl: (id, mode) => `/workspace/documents/${id}/pdf?mode=${mode}` },
  };
});
const { documentsApi } = await import('../../api/documents.js');

const TREE = {
  document_count: 3,
  synced_at: '2026-11-26T08:00:00Z',
  branches: [
    { name: 'Bộ điều khiển', used_by_chatbot: true, document_count: 2, folders: [
      { name: 'F54', documents: [
        { crm_id: 'a', doc_id: 'f54-operation-en', name: 'F54 - Operation Guide', status: 'review', chunk_count: 243, approved_count: 3, pending_count: 240, on_crm: true },
        { crm_id: 'b', doc_id: 'f54-installation-en', name: 'F54 - Installation Guide', status: 'review', chunk_count: 17, approved_count: 0, pending_count: 17, on_crm: true },
      ] },
    ] },
    { name: 'QS Servo', used_by_chatbot: false, document_count: 1, folders: [
      { name: 'SDV3', documents: [{ crm_id: 'c', doc_id: null, name: 'SDV3 manual', status: 'idle', chunk_count: 0, approved_count: 0, pending_count: 0, on_crm: true }] },
    ] },
  ],
};
const DETAIL = {
  crm_id: 'a', doc_id: 'f54-operation-en', name: 'F54 - Operation Guide', branch: 'Bộ điều khiển', folder: 'F54',
  document_type: 'operation', language: 'en', version: '1.0', status: 'review', chunk_count: 243, approved_count: 3,
  pending_count: 240, page_count: 170, on_crm: true,
};
const chunk = (id, extra = {}) => ({
  id, chunk_key: `B${id}`, chunk_index: id, chunk_type: 'procedure', section_path: ['PART 2', '2.3 Input', `2.3.${id} Step`],
  section_title: `2.3.${id} Step`, page_start: 17 + id, page_end: 17 + id, printed_page_start: 10, printed_page_end: 10,
  content: `2.3.${id} Step\nNội dung **${id}**`, summary_vi: null, keywords: [], review_status: 'draft', image_count: 0, images: [], ...extra,
});

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname}</p>;
}

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/documents" element={<><DocumentsPage /><Where /></>} />
        <Route path="/documents/:docId" element={<><DocumentsPage /><Where /></>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('Tài liệu & chunk (B6 phần đọc)', () => {
  beforeEach(() => {
    documentsApi.tree.mockReset().mockResolvedValue(TREE);
    documentsApi.detail.mockReset().mockResolvedValue(DETAIL);
    documentsApi.outline.mockReset().mockResolvedValue({ doc_id: 'f54-operation-en', total: 3, nodes: [
      { title: 'PART 2', path: ['PART 2'], chunk_count: 3, children: [{ title: '2.3 Input', path: ['PART 2', '2.3 Input'], chunk_count: 3, children: [] }] },
    ] });
    documentsApi.chunks.mockReset().mockResolvedValue({ doc_id: 'f54-operation-en', total: 25, offset: 0, limit: 20, items: [chunk(1), chunk(2, { review_status: 'approved' })] });
  });

  it('/documents mở tài liệu đầu tiên có đoạn; thanh trên có tên, trạng thái, link PDF', async () => {
    renderAt('/documents');
    await waitFor(() => expect(screen.getByTestId('where').textContent).toBe('/documents/f54-operation-en'));
    expect(await screen.findByRole('heading', { level: 1, name: 'F54 - Operation Guide' })).toBeTruthy();
    expect(screen.getByText('Chờ duyệt · Đã duyệt 3 / 243 đoạn')).toBeTruthy();
    expect(screen.getByRole('link', { name: /Mở PDF trong tab mới/ }).getAttribute('href')).toBe('/workspace/documents/f54-operation-en/pdf?mode=view');
  });

  it('nút Thư mục ẩn/hiện cây; nhóm chatbot chưa dùng chữ xám; tài liệu đang xem được đánh dấu', async () => {
    renderAt('/documents/f54-operation-en');
    const button = await screen.findByRole('button', { name: /Thư mục/ });
    expect(button.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(button);
    const tree = await screen.findByRole('navigation', { name: 'Thư mục tài liệu' });
    expect(within(tree).getByRole('link', { name: /F54 - Operation Guide/ }).getAttribute('aria-current')).toBe('page');
    expect(within(tree).getAllByText('99+').length).toBeGreaterThan(0);   // 240 chờ duyệt: rút gọn 99+
    fireEvent.click(within(tree).getByRole('button', { name: /QS Servo/ }));
    expect(within(tree).getByText('Chatbot chưa dùng')).toBeTruthy();
    expect(within(tree).queryByRole('link', { name: /SDV3/ })).toBeNull();   // chưa có đoạn: không mở được
  });

  it('tab Chờ duyệt có bong bóng số; lọc gửi status; bấm đoạn thì PDF nhảy trang; tải thêm', async () => {
    renderAt('/documents/f54-operation-en');
    const pending = await screen.findByRole('tab', { name: 'Chờ duyệt (240 đoạn)' });
    expect(pending.textContent).toBe('Chờ duyệt99+');   // 240 > 99: rút gọn, số đủ trong aria-label
    expect(await screen.findByText('2 / 25 đoạn')).toBeTruthy();
    fireEvent.click(screen.getByRole('article', { name: '2.3.2 Step' }));
    expect(document.querySelector('iframe').getAttribute('src')).toBe('/workspace/documents/f54-operation-en/pdf?mode=view#page=19');
    documentsApi.chunks.mockResolvedValueOnce({ doc_id: 'x', total: 25, offset: 2, limit: 20, items: [chunk(3)] });
    fireEvent.click(screen.getByRole('button', { name: /Tải thêm/ }));
    expect(await screen.findByText('3 / 25 đoạn')).toBeTruthy();
    expect(documentsApi.chunks).toHaveBeenLastCalledWith('f54-operation-en', expect.objectContaining({ tab: 'all' }), { offset: 2 });
    fireEvent.click(pending);
    await waitFor(() => expect(documentsApi.chunks).toHaveBeenLastCalledWith('f54-operation-en', expect.objectContaining({ tab: 'pending' }), expect.anything()));
  });

  it('Mục lục lọc theo mục; có thể bỏ lọc', async () => {
    renderAt('/documents/f54-operation-en');
    fireEvent.click(await screen.findByRole('button', { name: 'Mục lục' }));
    fireEvent.click(await screen.findByRole('button', { name: /2.3 Input/ }));
    expect(await screen.findByText('Đang lọc mục: 2.3 Input')).toBeTruthy();
    await waitFor(() => expect(documentsApi.chunks).toHaveBeenLastCalledWith('f54-operation-en', expect.objectContaining({ section: ['PART 2', '2.3 Input'] }), expect.anything()));
    fireEvent.click(screen.getByRole('button', { name: 'Bỏ lọc mục' }));
    expect(screen.queryByText('Đang lọc mục: 2.3 Input')).toBeNull();
  });

  it('bấm ảnh mở cửa sổ xem hình; ‹ › và phím chuyển hình; Mở trang trong PDF; Esc đóng', async () => {
    const images = [{ url: 'https://x/a.png', page: 20, printed_page: 12 }, { url: 'https://x/b.png', page: 21, printed_page: 13 }];
    documentsApi.chunks.mockResolvedValue({ doc_id: 'f54-operation-en', total: 1, offset: 0, limit: 20,
      items: [chunk(1, { content: '2.3.1 Step\nFigure 1. Mặt trước\nFigure 2. Mặt sau', image_count: 2, images })] });
    renderAt('/documents/f54-operation-en');
    fireEvent.click(await screen.findByRole('button', { name: 'Phóng to: Figure 1. Mặt trước' }));
    const dialog = screen.getByRole('dialog', { name: 'Xem hình phóng to' });
    expect(within(dialog).getByText('Figure 1. Mặt trước')).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Hình sau' }));
    expect(within(dialog).getByText('Figure 2. Mặt sau')).toBeTruthy();
    fireEvent.keyDown(dialog, { key: 'ArrowRight' });
    expect(within(dialog).getByText('Figure 1. Mặt trước')).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('button', { name: /Mở trang này trong PDF/ }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.querySelector('iframe').getAttribute('src')).toMatch(/#page=20$/);
    fireEvent.click(screen.getByRole('button', { name: 'Phóng to: Figure 2. Mặt sau' }));
    fireEvent.keyDown(screen.getByRole('dialog'), { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('máy chủ chưa bật API tài liệu thì báo rõ', async () => {
    documentsApi.tree.mockRejectedValue(new ApiError({ status: 404, kind: 'not_found', code: 'not_found' }));
    renderAt('/documents');
    expect(await screen.findByText('Chưa bật API tài liệu')).toBeTruthy();
  });

  it('chunkParams: tab và tìm kiếm thành query của máy chủ', () => {
    expect(chunkParams({ tab: 'pending', q: ' homing ', section: ['PART 2'] })).toEqual({ status: 'draft', q: 'homing', section: ['PART 2'] });
    expect(chunkParams({ tab: 'images' })).toEqual({ has_images: true });
    expect(chunkParams()).toEqual({});
  });
});
