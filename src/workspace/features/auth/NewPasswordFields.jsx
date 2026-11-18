// Cặp ô "Mật khẩu mới" + "Nhập lại", dùng chung cho đổi mật khẩu và đặt lại mật khẩu.

import { PasswordField } from '../../components/ui.jsx';
import { S } from '../../strings.vi.js';

export default function NewPasswordFields({ idPrefix, values, errors, onChange }) {
  return (
    <>
      <PasswordField
        id={`${idPrefix}-next`}
        label={S.auth.newPassword}
        autoComplete="new-password"
        hint={S.auth.passwordHint}
        error={errors.next}
        value={values.next}
        onChange={onChange('next')}
      />
      <PasswordField
        id={`${idPrefix}-confirm`}
        label={S.auth.confirmPassword}
        autoComplete="new-password"
        error={errors.confirm}
        value={values.confirm}
        onChange={onChange('confirm')}
      />
    </>
  );
}
