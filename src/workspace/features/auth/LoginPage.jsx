// Màn đăng nhập (mock M1, mục 14.3). Đăng nhập đúng → về `next` (mặc định Lịch sử hội thoại);
// tài khoản phải đổi mật khẩu thì RequireAuth chuyển tiếp sang /change-password.

import { useEffect, useState } from 'react';
import { Navigate, useLocation, useSearchParams } from 'react-router-dom';
import { USE_FIXTURES } from '../../config.js';
import { FIXTURE_HINTS } from '../../api/fixtures/auth.js';
import { safeNext } from '../../auth/paths.js';
import { useAuth } from '../../auth/useAuth.js';
import { Button, ErrorBanner, PasswordField, TextField } from '../../components/ui.jsx';
import { S } from '../../strings.vi.js';
import AuthLayout from './AuthLayout.jsx';
import { authErrorMessage, loginErrorMessage } from './authMessages.js';
import styles from './auth.module.css';

export default function LoginPage() {
  const auth = useAuth();
  const location = useLocation();
  const [params] = useSearchParams();
  const next = safeNext(params.get('next'));
  const notice = location.state?.notice;
  const [email, setEmail] = useState(location.state?.email || '');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  // Con trỏ vào ô còn trống đầu tiên (email, hoặc mật khẩu khi email đã điền sẵn sau đặt lại).
  useEffect(() => {
    document.getElementById(location.state?.email ? 'login-password' : 'login-email')?.focus();
  }, [location.state?.email]);

  if (auth.status === 'authenticated') return <Navigate to={next} replace />;

  const edit = (setter) => (event) => {
    setter(event.target.value);
    if (error) setError('');
  };

  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    if (!email.trim() || !password) {
      setError(S.auth.missingCredentials);
      return;
    }
    setBusy(true);
    setError('');
    try {
      // Thành công: AuthProvider chuyển sang authenticated, màn này render <Navigate> ở trên.
      await auth.login({ email: email.trim(), password });
    } catch (err) {
      setError(loginErrorMessage(err));
      setBusy(false);
    }
  };

  const devHints = USE_FIXTURES && (
    <aside className={styles.devHints} aria-label={S.auth.devHintsTitle}>
      <strong>{S.auth.devHintsTitle}</strong>
      <ul>
        {FIXTURE_HINTS.map((hint) => <li key={hint}>{hint}</li>)}
      </ul>
    </aside>
  );

  return (
    <AuthLayout title={S.auth.loginTitle} description={S.auth.audience} footer={devHints}>
      <form className={styles.form} onSubmit={submit} noValidate>
        {auth.status === 'unavailable' && !error && (
          <ErrorBanner tone="warning" error={auth.error} message={authErrorMessage(auth.error)} onRetry={auth.reload} />
        )}
        {notice === 'passwordReset' && !error && <ErrorBanner tone="success" message={S.auth.passwordResetDone} />}
        {error && <ErrorBanner message={error} />}
        <TextField
          id="login-email"
          label={S.auth.email}
          type="email"
          inputMode="email"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          placeholder={S.auth.emailPlaceholder}
          value={email}
          onChange={edit(setEmail)}
        />
        <PasswordField id="login-password" label={S.auth.password} autoComplete="current-password" value={password} onChange={edit(setPassword)} />
        <Button type="submit" variant="primary" block className={styles.submit} loading={busy} loadingLabel={S.auth.loggingIn}>
          {S.auth.login}
        </Button>
      </form>
    </AuthLayout>
  );
}
