// Đổi mật khẩu (mục 14.3). Bắt buộc khi `must_change_password` (tài khoản mới hoặc admin vừa đặt lại):
// RequireAuth chặn mọi trang khác cho tới khi đổi xong; nút phụ là Đăng xuất. Không bắt buộc thì nút
// phụ là Huỷ (dùng cho màn Hồ sơ sau này).

import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../../api/auth.js';
import { safeNext } from '../../auth/paths.js';
import { useAuth } from '../../auth/useAuth.js';
import { useToast } from '../../components/toast/useToast.js';
import { Button, ErrorBanner, PasswordField } from '../../components/ui.jsx';
import { S } from '../../strings.vi.js';
import AuthLayout from './AuthLayout.jsx';
import NewPasswordFields from './NewPasswordFields.jsx';
import { authErrorMessage, passwordFieldError, validateNewPassword } from './authMessages.js';
import { usePasswordForm } from './usePasswordForm.js';
import styles from './auth.module.css';

const ID = 'change-password';
const ORDER = ['current', 'next', 'confirm'];

export default function ChangePasswordPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const toast = useToast();
  const [params] = useSearchParams();
  const next = safeNext(params.get('next'));
  const email = auth.user?.email || '';
  const forced = Boolean(auth.user?.must_change_password);
  const form = usePasswordForm(ID, { current: '', next: '', confirm: '' });
  const { values, errors, busy } = form;

  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    const found = validateNewPassword({ email, ...values });
    if (Object.keys(found).length) {
      form.showErrors(found, ORDER);
      return;
    }
    form.setBusy(true);
    try {
      const data = await authApi.changePassword({ current_password: values.current, new_password: values.next });
      if (data?.user) auth.setUser(data.user);
      else auth.reload();
      toast.show({ message: S.auth.changed, tone: 'success' });
      navigate(next, { replace: true });
    } catch (err) {
      form.setBusy(false);
      if (err?.kind === 'unauthorized' || err?.kind === 'aborted') return; // hết phiên: client đã chuyển về đăng nhập
      const fieldError = passwordFieldError(err);
      if (fieldError) form.showErrors({ [fieldError.field]: fieldError.message }, ORDER);
      else form.setFormError(err);
    }
  };

  return (
    <AuthLayout title={S.auth.changeTitle} description={forced ? S.auth.changeForcedBody : S.auth.changeBody}>
      <form className={styles.form} onSubmit={submit} noValidate>
        {form.formError && <ErrorBanner error={form.formError} message={authErrorMessage(form.formError)} />}
        {/* Cho trình quản lý mật khẩu biết mật khẩu mới thuộc tài khoản nào. */}
        <input type="email" name="username" autoComplete="username" value={email} readOnly hidden />
        <p className={styles.meta}>{S.auth.signedInAs(email)}</p>
        <PasswordField
          id={`${ID}-current`}
          label={S.auth.currentPassword}
          autoComplete="current-password"
          error={errors.current}
          value={values.current}
          onChange={form.onChange('current')}
        />
        <NewPasswordFields idPrefix={ID} values={values} errors={errors} onChange={form.onChange} />
        <div className={styles.actions}>
          <Button type="submit" variant="primary" block className={styles.submit} loading={busy} loadingLabel={S.auth.saving}>
            {S.auth.savePassword}
          </Button>
          {forced ? (
            <Button variant="ghost" block onClick={auth.logout} disabled={busy}>{S.account.logout}</Button>
          ) : (
            <Button variant="ghost" block onClick={() => navigate(next)} disabled={busy}>{S.common.cancel}</Button>
          )}
        </div>
      </form>
    </AuthLayout>
  );
}
