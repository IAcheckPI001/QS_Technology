// Đặt lại mật khẩu từ link admin cấp (/reset-password?token=…, mục 14.2–14.3): link dùng một lần,
// hạn 30 phút. Kiểm link ngay khi mở để báo hết hạn trước khi người dùng gõ mật khẩu.
// Đặt xong → về màn đăng nhập, điền sẵn email.

import { useNavigate, useSearchParams } from 'react-router-dom';
import { authApi } from '../../api/auth.js';
import { ApiError } from '../../api/errors.js';
import { LOGIN_PATH } from '../../auth/paths.js';
import { Button, ErrorBanner, SkeletonBlock } from '../../components/ui.jsx';
import { useResource } from '../../hooks/useResource.js';
import { S } from '../../strings.vi.js';
import AuthLayout from './AuthLayout.jsx';
import NewPasswordFields from './NewPasswordFields.jsx';
import { authErrorMessage, isResetLinkInvalid, passwordFieldError, validateNewPassword } from './authMessages.js';
import { usePasswordForm } from './usePasswordForm.js';
import styles from './auth.module.css';

const ID = 'reset-password';
const ORDER = ['next', 'confirm'];
const MISSING_TOKEN = new ApiError({ kind: 'validation', code: 'reset_token_invalid' });

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const token = params.get('token') || '';
  const check = useResource(
    ({ signal }) => (token ? authApi.verifyReset({ token }, { signal }) : Promise.reject(MISSING_TOKEN)),
    [token],
  );
  const form = usePasswordForm(ID, { next: '', confirm: '' });
  const { values, errors, busy } = form;
  const email = check.data?.email || '';
  const toLogin = () => navigate(LOGIN_PATH, { replace: true });

  if (check.loading) {
    return (
      <AuthLayout title={S.auth.resetTitle} description={S.auth.resetChecking}>
        <SkeletonBlock lines={3} label={S.auth.resetChecking} />
      </AuthLayout>
    );
  }

  if (isResetLinkInvalid(check.error) || (form.formError && isResetLinkInvalid(form.formError))) {
    return (
      <AuthLayout title={S.auth.resetInvalidTitle} description={S.auth.resetInvalidBody}>
        <Button variant="primary" block onClick={toLogin}>{S.auth.backToLogin}</Button>
      </AuthLayout>
    );
  }

  if (check.error) {
    return (
      <AuthLayout title={S.auth.resetTitle}>
        <ErrorBanner error={check.error} message={authErrorMessage(check.error)} onRetry={check.reload} />
      </AuthLayout>
    );
  }

  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    const found = validateNewPassword({ email, next: values.next, confirm: values.confirm });
    if (Object.keys(found).length) {
      form.showErrors(found, ORDER);
      return;
    }
    form.setBusy(true);
    try {
      await authApi.resetPassword({ token, new_password: values.next });
      navigate(LOGIN_PATH, { replace: true, state: { notice: 'passwordReset', email } });
    } catch (err) {
      form.setBusy(false);
      const fieldError = passwordFieldError(err);
      if (fieldError) form.showErrors({ [fieldError.field]: fieldError.message }, ORDER);
      else form.setFormError(err);
    }
  };

  return (
    <AuthLayout title={S.auth.resetTitle} description={email ? S.auth.resetBody(email) : undefined}>
      <form className={styles.form} onSubmit={submit} noValidate>
        {form.formError && <ErrorBanner error={form.formError} message={authErrorMessage(form.formError)} />}
        <input type="email" name="username" autoComplete="username" value={email} readOnly hidden />
        <NewPasswordFields idPrefix={ID} values={values} errors={errors} onChange={form.onChange} />
        <Button type="submit" variant="primary" block className={styles.submit} loading={busy} loadingLabel={S.auth.saving}>
          {S.auth.savePassword}
        </Button>
      </form>
    </AuthLayout>
  );
}
