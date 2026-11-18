// Khung chung của các màn ngoài app (đăng nhập, đổi và đặt lại mật khẩu) theo mock M1:
// logo + tên ở trên, một thẻ ở giữa; điện thoại bỏ viền thẻ, chữ và ô nhập lớn hơn.

import { useEffect, useId } from 'react';
import logo from '../../assets/qs-logo.png';
import { S } from '../../strings.vi.js';
import styles from './auth.module.css';

export default function AuthLayout({ title, description, children, footer }) {
  const headingId = useId();

  useEffect(() => {
    const previous = document.title;
    document.title = `${title} · ${S.appName}`;
    return () => {
      document.title = previous;
    };
  }, [title]);

  return (
    <main className={styles.screen}>
      <div className={styles.column}>
        <div className={styles.brand}>
          {/* Logo có chữ QS Technology, đã ghi ngay bên cạnh nên để alt rỗng. */}
          <img src={logo} alt="" width="72" height="40" />
          <div className={styles.brandText}>
            <strong>{S.appName}</strong>
            <span>{S.company}</span>
          </div>
        </div>
        <section className={styles.card} aria-labelledby={headingId}>
          <div className={styles.heading}>
            <h1 id={headingId}>{title}</h1>
            {description && <p>{description}</p>}
          </div>
          {children}
        </section>
        {footer}
      </div>
    </main>
  );
}
