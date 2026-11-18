import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthContext } from '../auth/AuthContext.js';
import AppShell from './AppShell.jsx';

// Widget chat cũ có i18n và gọi widget-backend; không thuộc phạm vi test khung app.
vi.mock('../../components/ChatbotWidget.jsx', () => ({ default: () => null }));

function renderShell(permissions) {
  const user = { display_name: 'Quản trị viên', email: 'admin@qstcnc.com', role: 'admin', permissions };
  return render(
    <AuthContext.Provider value={{ status: 'authenticated', user, logout: vi.fn() }}>
      <MemoryRouter initialEntries={['/conversations']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/conversations" element={<p>trang hội thoại</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

beforeEach(() => localStorage.clear());

describe('AppShell', () => {
  it('ẩn mục điều hướng không đủ quyền và đánh dấu mục đang xem', () => {
    renderShell(['conversations:read', 'chunks:read']);
    const sidebar = screen.getByLabelText('Thanh bên');
    const links = within(sidebar).getAllByRole('link').map((a) => a.textContent);
    expect(links).toEqual(['Lịch sử hội thoại', 'Tài liệu & chunk']);
    expect(within(sidebar).getByRole('link', { name: 'Lịch sử hội thoại' }).getAttribute('aria-current')).toBe('page');
  });

  it('thu gọn sidebar và nhớ trạng thái', () => {
    const { unmount } = renderShell(['conversations:read']);
    fireEvent.click(screen.getByLabelText('Thu gọn menu'));
    expect(screen.getByLabelText('Mở rộng menu').getAttribute('aria-expanded')).toBe('false');
    expect(localStorage.getItem('ws.sidebarCollapsed')).toBe('true');
    unmount();
    renderShell(['conversations:read']);
    expect(screen.getByLabelText('Mở rộng menu')).toBeTruthy();
  });

  it('khối tài khoản ghim đáy có tên, email và Đăng xuất', () => {
    renderShell(['conversations:read']);
    const sidebar = screen.getByLabelText('Thanh bên');
    expect(within(sidebar).getByText('Quản trị viên')).toBeTruthy();
    expect(within(sidebar).getByText(/admin@qstcnc.com/)).toBeTruthy();
    expect(within(sidebar).getByRole('button', { name: 'Đăng xuất' })).toBeTruthy();
  });
});
