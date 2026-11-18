import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { ApiError } from '../../api/errors.js';
import { AuthContext } from '../../auth/AuthContext.js';
import { RequireAuth } from '../../auth/guards.jsx';
import ToastProvider from '../../components/toast/ToastProvider.jsx';
import { formatUnlockTime, loginErrorMessage, passwordFieldError, validateNewPassword } from './authMessages.js';
import ChangePasswordPage from './ChangePasswordPage.jsx';
import LoginPage from './LoginPage.jsx';
import ResetPasswordPage from './ResetPasswordPage.jsx';

vi.mock('../../api/auth.js', () => ({
  authApi: { changePassword: vi.fn(), verifyReset: vi.fn(), resetPassword: vi.fn() },
}));
const { authApi } = await import('../../api/auth.js');

const STRONG = 'mot cum tu du dai';

function Where() {
  const location = useLocation();
  return <p data-testid="where">{location.pathname}{location.search}|{location.state?.notice || ''}|{location.state?.email || ''}</p>;
}

function renderAt(path, auth, routes) {
  return render(
    <ToastProvider>
      <AuthContext.Provider value={{ status: 'anonymous', user: null, reload: vi.fn(), logout: vi.fn(), setUser: vi.fn(), login: vi.fn(), ...auth }}>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            {routes}
            <Route path="*" element={<Where />} />
          </Routes>
        </MemoryRouter>
      </AuthContext.Provider>
    </ToastProvider>,
  );
}

const type = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

describe('luật mật khẩu', () => {
  it('tối thiểu 12 ký tự, không trùng email, khác mật khẩu cũ, nhập lại khớp', () => {
    expect(validateNewPassword({ next: 'ngan', confirm: 'ngan' })).toEqual({ next: expect.stringMatching(/12 ký tự/) });
    expect(validateNewPassword({ email: 'An@qstcnc.com', next: 'an@qstcnc.com', confirm: 'an@qstcnc.com' }).next).toMatch(/trùng email/);
    expect(validateNewPassword({ current: STRONG, next: STRONG, confirm: STRONG }).next).toMatch(/khác mật khẩu hiện tại/);
    expect(validateNewPassword({ next: STRONG, confirm: `${STRONG}x` })).toEqual({ confirm: expect.stringMatching(/không khớp/) });
    expect(validateNewPassword({ current: '', next: STRONG, confirm: STRONG })).toEqual({ current: expect.any(String) });
    expect(validateNewPassword({ current: 'cu-mat-khau-12', next: STRONG, confirm: STRONG })).toEqual({});
  });

  it('đổi mã lỗi API thành lỗi của ô', () => {
    expect(passwordFieldError({ code: 'invalid_current_password' })).toEqual({ field: 'current', message: expect.any(String) });
    expect(passwordFieldError({ code: 'server_error' })).toBeNull();
  });
});

describe('thông báo đăng nhập', () => {
  const now = new Date('2026-11-18T08:00:00');

  it('sai thông tin dùng một câu chung', () => {
    expect(loginErrorMessage(new ApiError({ status: 401, kind: 'unauthorized', code: 'invalid_credentials' }))).toBe('Email hoặc mật khẩu không đúng.');
    expect(loginErrorMessage(new ApiError({ status: 401, kind: 'unauthorized' }))).toBe('Email hoặc mật khẩu không đúng.');
  });

  it('tạm khoá thì nói giờ mở; vô hiệu thì bảo liên hệ admin', () => {
    const lockedUntil = new Date('2026-11-18T08:15:00').toISOString();
    const locked = new ApiError({ status: 423, code: 'account_locked', details: { locked_until: lockedUntil } });
    expect(loginErrorMessage(locked, now)).toContain(formatUnlockTime(lockedUntil, now));
    expect(formatUnlockTime(lockedUntil, now)).not.toContain('ngày');
    expect(loginErrorMessage(new ApiError({ status: 423, code: 'account_locked' }), now)).toMatch(/liên hệ admin/i);
    expect(loginErrorMessage(new ApiError({ status: 403, kind: 'forbidden', code: 'account_disabled' }))).toMatch(/vô hiệu/);
  });

  it('máy chủ chưa có B1 thì nói rõ', () => {
    expect(loginErrorMessage(new ApiError({ status: 404, kind: 'not_found' }))).toMatch(/B1/);
  });
});

describe('màn đăng nhập', () => {
  const routes = <Route path="/login" element={<LoginPage />} />;

  it('thiếu email hoặc mật khẩu thì báo, không gọi API', () => {
    const login = vi.fn();
    renderAt('/login', { login }, routes);
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }));
    expect(screen.getByRole('alert').textContent).toBe('Nhập email và mật khẩu.');
    expect(login).not.toHaveBeenCalled();
  });

  it('sai mật khẩu hiện câu chung; nút Hiện/Ẩn đổi kiểu ô', async () => {
    const login = vi.fn().mockRejectedValue(new ApiError({ status: 401, kind: 'unauthorized', code: 'invalid_credentials' }));
    renderAt('/login', { login }, routes);
    type('Email', ' admin@qstcnc.com ');
    type('Mật khẩu', 'sai');
    const toggle = screen.getByRole('button', { name: 'Hiện mật khẩu' });
    fireEvent.click(toggle);
    expect(screen.getByLabelText('Mật khẩu').getAttribute('type')).toBe('text');
    expect(toggle.getAttribute('aria-label')).toBe('Ẩn mật khẩu');
    fireEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }));
    expect(login).toHaveBeenCalledWith({ email: 'admin@qstcnc.com', password: 'sai' });
    expect(await screen.findByText('Email hoặc mật khẩu không đúng.')).toBeTruthy();
  });

  it('đã đăng nhập thì chuyển tới next (chỉ đường dẫn nội bộ)', () => {
    renderAt('/login?next=%2Fkeys', { status: 'authenticated', user: { permissions: [] } }, routes);
    expect(screen.getByTestId('where').textContent).toMatch(/^\/keys\|/);
  });

  it('bỏ qua next trỏ ra ngoài', () => {
    renderAt('/login?next=https%3A%2F%2Fevil.example', { status: 'authenticated', user: { permissions: [] } }, routes);
    expect(screen.getByTestId('where').textContent).toMatch(/^\/conversations\|/);
  });
});

describe('đổi mật khẩu bắt buộc', () => {
  const user = { email: 'moi@qstcnc.com', permissions: [], must_change_password: true };
  const routes = (
    <Route element={<RequireAuth />}>
      <Route path="/change-password" element={<ChangePasswordPage />} />
      <Route path="/keys" element={<p>keys page</p>} />
    </Route>
  );

  it('chặn mọi trang khác, giữ trang định mở trong next', () => {
    renderAt('/keys', { status: 'authenticated', user }, routes);
    expect(screen.getByRole('heading', { name: 'Đổi mật khẩu' })).toBeTruthy();
    expect(screen.queryByText('keys page')).toBeNull();
    expect(screen.getByRole('button', { name: 'Đăng xuất' })).toBeTruthy();
  });

  it('kiểm ở trình duyệt trước, rồi gửi và chuyển tới next', async () => {
    const setUser = vi.fn();
    authApi.changePassword.mockResolvedValue({ user: { ...user, must_change_password: false } });
    renderAt('/change-password?next=%2Fdocuments', { status: 'authenticated', user, setUser }, routes);
    fireEvent.click(screen.getByRole('button', { name: 'Lưu mật khẩu mới' }));
    expect(authApi.changePassword).not.toHaveBeenCalled();
    expect(document.activeElement.id).toBe('change-password-current');

    type('Mật khẩu hiện tại', 'mat-khau-tam-thoi');
    type('Mật khẩu mới', STRONG);
    type('Nhập lại mật khẩu mới', STRONG);
    fireEvent.click(screen.getByRole('button', { name: 'Lưu mật khẩu mới' }));
    await waitFor(() => expect(screen.getByTestId('where').textContent).toMatch(/^\/documents\|/));
    expect(authApi.changePassword).toHaveBeenCalledWith({ current_password: 'mat-khau-tam-thoi', new_password: STRONG });
    expect(setUser).toHaveBeenCalledWith(expect.objectContaining({ must_change_password: false }));
  });

  it('server báo sai mật khẩu hiện tại thì gắn lỗi vào ô đó', async () => {
    authApi.changePassword.mockRejectedValue(new ApiError({ status: 400, kind: 'validation', code: 'invalid_current_password' }));
    renderAt('/change-password', { status: 'authenticated', user }, routes);
    type('Mật khẩu hiện tại', 'mat-khau-sai-123');
    type('Mật khẩu mới', STRONG);
    type('Nhập lại mật khẩu mới', STRONG);
    fireEvent.click(screen.getByRole('button', { name: 'Lưu mật khẩu mới' }));
    expect(await screen.findByText('Mật khẩu hiện tại không đúng.')).toBeTruthy();
    expect(screen.getByLabelText('Mật khẩu hiện tại').getAttribute('aria-invalid')).toBe('true');
  });
});

describe('đặt lại mật khẩu', () => {
  const routes = <Route path="/reset-password" element={<ResetPasswordPage />} />;

  it('link hết hạn hoặc đã dùng thì báo ngay, không hiện form', async () => {
    authApi.verifyReset.mockRejectedValue(new ApiError({ status: 410, code: 'reset_token_invalid' }));
    renderAt('/reset-password?token=cu', {}, routes);
    expect(await screen.findByRole('heading', { name: 'Link không còn hiệu lực' })).toBeTruthy();
    expect(screen.queryByLabelText('Mật khẩu mới')).toBeNull();
  });

  it('thiếu token cũng coi là link hỏng', async () => {
    renderAt('/reset-password', {}, routes);
    expect(await screen.findByRole('heading', { name: 'Link không còn hiệu lực' })).toBeTruthy();
  });

  it('đặt xong về đăng nhập, điền sẵn email', async () => {
    authApi.verifyReset.mockResolvedValue({ email: 'kythuat@qstcnc.com' });
    authApi.resetPassword.mockResolvedValue(null);
    renderAt('/reset-password?token=demo', {}, routes);
    expect(await screen.findByText('Đặt mật khẩu mới cho kythuat@qstcnc.com.')).toBeTruthy();
    type('Mật khẩu mới', STRONG);
    type('Nhập lại mật khẩu mới', STRONG);
    fireEvent.click(screen.getByRole('button', { name: 'Lưu mật khẩu mới' }));
    await waitFor(() => expect(screen.getByTestId('where').textContent).toBe('/login|passwordReset|kythuat@qstcnc.com'));
    expect(authApi.resetPassword).toHaveBeenCalledWith({ token: 'demo', new_password: STRONG });
  });
});
