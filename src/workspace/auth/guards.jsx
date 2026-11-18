// Chặn route: chưa đăng nhập → /login?next=…; phải đổi mật khẩu → /change-password?next=…;
// thiếu quyền → trang Không đủ quyền (mục 14.3).

import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { S } from '../strings.vi.js';
import { ErrorBanner, SkeletonBlock } from '../components/ui.jsx';
import ForbiddenPage from '../pages/ForbiddenPage.jsx';
import { CHANGE_PASSWORD_PATH, changePasswordPath, loginPath } from './paths.js';
import { can } from './permissions.js';
import { useAuth } from './useAuth.js';
import styles from '../pages/pages.module.css';

export function RequireAuth() {
  const auth = useAuth();
  const location = useLocation();
  if (auth.status === 'loading') {
    return (
      <div className={styles.center}>
        <div className={styles.narrow}><SkeletonBlock lines={4} /></div>
      </div>
    );
  }
  if (auth.status === 'unavailable') {
    return (
      <div className={styles.center}>
        <div className={styles.narrow}>
          <ErrorBanner error={auth.error} message={auth.error?.kind === 'not_found' ? S.errors.authUnavailable : undefined} onRetry={auth.reload} />
        </div>
      </div>
    );
  }
  if (auth.status !== 'authenticated') return <Navigate to={loginPath(location)} replace />;
  // Tài khoản mới hoặc vừa được admin đặt lại: phải đổi mật khẩu trước khi dùng Workspace.
  if (auth.user?.must_change_password && location.pathname !== CHANGE_PASSWORD_PATH) {
    return <Navigate to={changePasswordPath(location)} replace />;
  }
  return <Outlet />;
}

export function RequirePermission({ permission, children }) {
  const { user } = useAuth();
  return can(user, permission) ? children : <ForbiddenPage />;
}
