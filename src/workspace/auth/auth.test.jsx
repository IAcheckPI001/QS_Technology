import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { AuthContext } from './AuthContext.js';
import { RequireAuth, RequirePermission } from './guards.jsx';
import { loginPath, safeNext } from './paths.js';
import { can } from './permissions.js';

function LoginProbe() {
  const location = useLocation();
  return <p>login {location.search}</p>;
}

function renderGuarded(auth, path = '/keys?x=1') {
  return render(
    <AuthContext.Provider value={{ reload: () => {}, ...auth }}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/login" element={<LoginProbe />} />
          <Route element={<RequireAuth />}>
            <Route path="/keys" element={<RequirePermission permission="service_keys:manage"><p>keys page</p></RequirePermission>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </AuthContext.Provider>,
  );
}

describe('đường dẫn đăng nhập', () => {
  it('giữ trang đang xem trong next', () => {
    expect(loginPath({ pathname: '/keys', search: '?a=1' })).toBe('/login?next=%2Fkeys%3Fa%3D1');
    expect(loginPath({ pathname: '/', search: '' })).toBe('/login');
  });

  it('chỉ nhận next nội bộ (chống chuyển hướng ra site khác)', () => {
    expect(safeNext('/documents')).toBe('/documents');
    expect(safeNext('https://evil.example')).toBe('/conversations');
    expect(safeNext('//evil.example')).toBe('/conversations');
    expect(safeNext(null)).toBe('/conversations');
  });
});

describe('chặn route', () => {
  it('chưa đăng nhập → /login kèm next', () => {
    renderGuarded({ status: 'anonymous', user: null });
    expect(screen.getByText(/login/).textContent).toContain('next=%2Fkeys%3Fx%3D1');
  });

  it('đủ quyền thì vào trang, thiếu quyền thì báo không đủ quyền', () => {
    const { unmount } = renderGuarded({ status: 'authenticated', user: { permissions: ['service_keys:manage'] } });
    expect(screen.getByText('keys page')).toBeTruthy();
    unmount();
    renderGuarded({ status: 'authenticated', user: { permissions: [] } });
    expect(screen.getByText('Không đủ quyền')).toBeTruthy();
  });

  it('máy chủ chưa có đăng nhập (B1) thì báo rõ, không chuyển trang', () => {
    renderGuarded({ status: 'unavailable', user: null, error: { kind: 'not_found' } });
    expect(screen.getByRole('alert').textContent).toMatch(/B1/);
  });

  it('kiểm quyền, không kiểm vai trò', () => {
    expect(can({ role: 'admin', permissions: [] }, 'users:manage')).toBe(false);
    expect(can({ role: 'reviewer', permissions: ['users:manage'] }, 'users:manage')).toBe(true);
  });
});
