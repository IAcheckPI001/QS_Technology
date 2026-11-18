// Người dùng hiện tại và phiên (mục 14.3): tải /me khi mở app; 401 ở bất kỳ API nào → về
// /login?next=<đường dẫn đang xem>. Khi backend chưa có B1 (404/lỗi mạng) báo "unavailable".

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth.js';
import { setUnauthorizedHandler } from '../api/client.js';
import { AuthContext } from './AuthContext.js';
import { loginPath } from './paths.js';

export default function AuthProvider({ children }) {
  const [state, setState] = useState({ status: 'loading', user: null, error: null });
  const [nonce, setNonce] = useState(0);
  const navigate = useNavigate();

  useEffect(() => {
    const controller = new AbortController();
    authApi
      .me({ signal: controller.signal })
      .then((data) => setState({ status: 'authenticated', user: data.user, error: null }))
      .catch((error) => {
        if (controller.signal.aborted || error?.kind === 'aborted') return;
        if (error?.kind === 'unauthorized') setState({ status: 'anonymous', user: null, error: null });
        else setState({ status: 'unavailable', user: null, error });
      });
    return () => controller.abort();
  }, [nonce]);

  // Hết phiên giữa chừng: chuyển về đăng nhập, giữ đường dẫn để quay lại.
  useEffect(
    () =>
      setUnauthorizedHandler(() => {
        setState({ status: 'anonymous', user: null, error: null });
        navigate(loginPath(window.location), { replace: true });
      }),
    [navigate],
  );

  const login = useCallback(async (credentials) => {
    const data = await authApi.login(credentials);
    setState({ status: 'authenticated', user: data.user, error: null });
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      setState({ status: 'anonymous', user: null, error: null });
      navigate('/login', { replace: true });
    }
  }, [navigate]);

  const reload = useCallback(() => {
    setState({ status: 'loading', user: null, error: null });
    setNonce((n) => n + 1);
  }, []);

  // Đổi mật khẩu xong: backend trả user mới (must_change_password = false), cập nhật không cần tải lại /me.
  const setUser = useCallback((user) => setState({ status: 'authenticated', user, error: null }), []);

  const value = useMemo(() => ({ ...state, login, logout, reload, setUser }), [state, login, logout, reload, setUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
