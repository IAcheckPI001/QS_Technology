// Điểm vào Workspace (FRONTEND_REQUIREMENTS.md mục 18). Route theo 18.2; các màn chưa dựng hiện
// trang "đang xây dựng" kèm giai đoạn, không giả làm tính năng.

import { Navigate, Route, Routes } from 'react-router-dom';
import './styles/tokens.css';
import AuthProvider from './auth/AuthProvider.jsx';
import { RequireAuth, RequirePermission } from './auth/guards.jsx';
import { PERMISSIONS } from './auth/permissions.js';
import ToastProvider from './components/toast/ToastProvider.jsx';
import AppShell from './layout/AppShell.jsx';
import ChangePasswordPage from './features/auth/ChangePasswordPage.jsx';
import LoginPage from './features/auth/LoginPage.jsx';
import ResetPasswordPage from './features/auth/ResetPasswordPage.jsx';
import NotFoundPage from './pages/NotFoundPage.jsx';
import PlaceholderPage from './pages/PlaceholderPage.jsx';
import { S } from './strings.vi.js';

function guarded(permission, element) {
  return <RequirePermission permission={permission}>{element}</RequirePermission>;
}

export default function WorkspaceApp() {
  return (
    <div className="ws-root">
      <ToastProvider>
        <AuthProvider>
          <Routes>
            <Route path="login" element={<LoginPage />} />
            <Route path="reset-password" element={<ResetPasswordPage />} />
            <Route element={<RequireAuth />}>
              <Route path="change-password" element={<ChangePasswordPage />} />
              <Route element={<AppShell />}>
                <Route index element={<Navigate to="/conversations" replace />} />
                <Route path="conversations" element={guarded(PERMISSIONS.conversationsRead, <PlaceholderPage title={S.nav.conversations} phase={2} />)} />
                <Route path="conversations/:sessionId/*" element={guarded(PERMISSIONS.conversationsRead, <PlaceholderPage title="Chi tiết hội thoại" phase={2} />)} />
                <Route path="documents/*" element={guarded(PERMISSIONS.chunksRead, <PlaceholderPage title={S.nav.documents} phase={5} />)} />
                <Route path="keys" element={guarded(PERMISSIONS.serviceKeysManage, <PlaceholderPage title={S.nav.keys} phase={3} />)} />
                <Route path="users" element={guarded(PERMISSIONS.usersManage, <PlaceholderPage title={S.nav.users} phase={4} />)} />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Route>
          </Routes>
        </AuthProvider>
      </ToastProvider>
    </div>
  );
}
