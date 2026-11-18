// Thông báo nổi (18.3, mục 16): thành công/thông tin tự ẩn sau 6 giây và có thể "Hoàn tác";
// lỗi không tự ẩn và có hành động (vd. Thử lại).

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { X } from 'lucide-react';
import { S } from '../../strings.vi.js';
import { ToastContext } from './ToastContext.js';
import styles from './Toast.module.css';

export const TOAST_DURATION = 6000;
let seq = 0;

export default function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef(new Map());

  const dismiss = useCallback((id) => {
    clearTimeout(timers.current.get(id));
    timers.current.delete(id);
    setToasts((list) => list.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback(
    ({ message, tone = 'info', undo, action, duration }) => {
      seq += 1;
      const id = seq;
      setToasts((list) => [...list, { id, message, tone, undo, action }]);
      const ms = duration ?? (tone === 'error' ? null : TOAST_DURATION);
      if (ms) timers.current.set(id, setTimeout(() => dismiss(id), ms));
      return id;
    },
    [dismiss],
  );

  useEffect(() => {
    const map = timers.current;
    return () => map.forEach((timer) => clearTimeout(timer));
  }, []);

  const value = useMemo(() => ({ show, dismiss }), [show, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className={styles.region} aria-live="polite" aria-relevant="additions">
        {toasts.map((toast) => (
          <div key={toast.id} className={`${styles.toast} ${toast.tone === 'error' ? styles.error : ''}`} role={toast.tone === 'error' ? 'alert' : 'status'}>
            <span className={styles.message}>{toast.message}</span>
            {toast.undo && (
              <button type="button" className={styles.action} onClick={() => { toast.undo(); dismiss(toast.id); }}>{S.common.undo}</button>
            )}
            {toast.action && (
              <button type="button" className={styles.action} onClick={() => { toast.action.onClick(); dismiss(toast.id); }}>{toast.action.label}</button>
            )}
            <button type="button" className={styles.close} aria-label={S.common.closeNotice} onClick={() => dismiss(toast.id)}>
              <X size={16} aria-hidden="true" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
