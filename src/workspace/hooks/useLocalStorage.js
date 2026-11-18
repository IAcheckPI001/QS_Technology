// Ghi nhớ tuỳ chọn của người xem (vd. sidebar thu gọn, Q22). Storage có thể bị chặn: luôn có giá trị mặc định.

import { useCallback, useState } from 'react';

export function useLocalStorage(key, fallback) {
  const [value, setValue] = useState(() => {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? fallback : JSON.parse(raw);
    } catch {
      return fallback;
    }
  });

  const update = useCallback(
    (next) => {
      setValue((prev) => {
        const resolved = typeof next === 'function' ? next(prev) : next;
        try {
          localStorage.setItem(key, JSON.stringify(resolved));
        } catch {
          /* Không lưu được thì chỉ giữ trong phiên. */
        }
        return resolved;
      });
    },
    [key],
  );

  return [value, update];
}
