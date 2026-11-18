// Trạng thái form mật khẩu: giá trị, lỗi từng ô, lỗi chung, đang gửi. Sửa một ô thì xoá lỗi của ô đó.

import { useCallback, useState } from 'react';

export function usePasswordForm(idPrefix, initial) {
  const [values, setValues] = useState(initial);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [busy, setBusy] = useState(false);

  const onChange = useCallback(
    (field) => (event) => {
      const { value } = event.target;
      setValues((prev) => ({ ...prev, [field]: value }));
      setErrors((prev) => (prev[field] ? { ...prev, [field]: undefined } : prev));
      setFormError(null);
    },
    [],
  );

  /** Gắn lỗi vào ô và đưa con trỏ tới ô lỗi đầu tiên theo thứ tự trên form. */
  const showErrors = useCallback(
    (found, order) => {
      setErrors(found);
      const first = order.find((field) => found[field]);
      if (first) document.getElementById(`${idPrefix}-${first}`)?.focus();
    },
    [idPrefix],
  );

  return { values, errors, formError, setFormError, busy, setBusy, onChange, showErrors };
}
