// Cửa sổ nổi dùng chung (18.3): giữ focus bên trong, Esc đóng (bắt phím trên chính lớp phủ),
// trả focus về phần tử đã mở khi đóng; ≤ 720px hiển thị dạng sheet.

import { useEffect, useId, useRef } from 'react';
import { X } from 'lucide-react';
import { S } from '../strings.vi.js';
import { IconButton } from './ui.jsx';
import { focusableIn } from './focus.js';
import styles from './Overlay.module.css';

/**
 * dismissible=false: bấm nền không đóng (vd. cửa sổ hiện khóa một lần, Q27); Esc gọi onEscape nếu có,
 * nếu không thì onClose. role="alertdialog" cho xác nhận thao tác nguy hiểm.
 */
export default function Modal({ open, onClose, onEscape, title, description, children, footer, dismissible = true, role = 'dialog', wide, showClose = true }) {
  const dialogRef = useRef(null);
  const returnFocusRef = useRef(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    if (!open) return undefined;
    returnFocusRef.current = document.activeElement;
    const node = dialogRef.current;
    const preferred = node?.querySelector('[data-autofocus]');
    (preferred || focusableIn(node)[0] || node)?.focus();
    return () => {
      const target = returnFocusRef.current;
      if (target && typeof target.focus === 'function' && document.contains(target)) target.focus();
    };
  }, [open]);

  if (!open) return null;

  const handleKeyDown = (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      (onEscape || onClose)?.();
      return;
    }
    if (event.key !== 'Tab') return;
    const items = focusableIn(dialogRef.current);
    if (!items.length) {
      event.preventDefault();
      return;
    }
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return (
    <div className={styles.scrim} onMouseDown={(event) => { if (dismissible && event.target === event.currentTarget) onClose?.(); }} onKeyDown={handleKeyDown}>
      <div
        ref={dialogRef}
        className={`${styles.dialog} ${wide ? styles.wide : ''}`}
        role={role}
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descriptionId : undefined}
        tabIndex={-1}
      >
        <div className={styles.head}>
          <div className={styles.titleWrap}>
            <h2 id={titleId} className={styles.title}>{title}</h2>
            {description && <p id={descriptionId} className={styles.description}>{description}</p>}
          </div>
          {showClose && dismissible && <IconButton icon={X} label={S.common.close} onClick={onClose} />}
        </div>
        <div className={styles.body}>{children}</div>
        {footer && <div className={styles.foot}>{footer}</div>}
      </div>
    </div>
  );
}
