// Thành phần cơ bản của Workspace (FRONTEND_REQUIREMENTS.md 18.3). Chỉ export component.

import { useId, useState } from 'react';
import { AlertCircle, CheckCircle2, Eye, EyeOff, RotateCw } from 'lucide-react';
import { S } from '../strings.vi.js';
import { userMessage } from '../api/errors.js';
import styles from './ui.module.css';

const cx = (...names) => names.filter(Boolean).join(' ');

const VARIANT = {
  secondary: '',
  primary: styles.primary,
  approve: styles.approve,
  danger: styles.danger,
  dangerOutline: styles.dangerOutline,
  ghost: styles.ghost,
};

// Lưu ý lint: cấu hình ESLint của repo không đánh dấu biến dùng trong JSX là "đã dùng" khi nó là tham số
// tách từ props, nên gán lại vào biến viết hoa (khớp varsIgnorePattern ^[A-Z_]).
export function Button({ variant = 'secondary', size, block, icon, loading, loadingLabel, children, className, type = 'button', disabled, ...rest }) {
  const Icon = icon;
  return (
    <button
      type={type}
      className={cx(styles.button, VARIANT[variant], size === 'small' && styles.small, block && styles.block, className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {Icon && <Icon size={16} aria-hidden="true" />}
      {loading && loadingLabel ? loadingLabel : children}
    </button>
  );
}

/** Nút chỉ có icon: bắt buộc `label` cho trình đọc màn hình và tooltip. */
export function IconButton({ icon, label, outline, size = 18, className, type = 'button', ...rest }) {
  const Icon = icon;
  return (
    <button type={type} className={cx(styles.iconButton, outline && styles.iconButtonOutline, className)} aria-label={label} title={label} {...rest}>
      <Icon size={size} aria-hidden="true" />
    </button>
  );
}

export function Badge({ tone = 'neutral', children, className, ...rest }) {
  return (
    <span className={cx(styles.badge, styles[`tone-${tone}`], className)} {...rest}>
      {children}
    </span>
  );
}

export function Card({ as = 'section', className, children, ...rest }) {
  const Tag = as;
  return (
    <Tag className={cx(styles.card, className)} {...rest}>
      {children}
    </Tag>
  );
}

function useFieldIds(id) {
  const auto = useId();
  const base = id || auto;
  return { controlId: base, hintId: `${base}-hint`, errorId: `${base}-error` };
}

function describedBy(hint, error, ids) {
  return [hint && ids.hintId, error && ids.errorId].filter(Boolean).join(' ') || undefined;
}

export function TextField({ label, hint, error, id, multiline, className, ...rest }) {
  const ids = useFieldIds(id);
  const Control = multiline ? 'textarea' : 'input';
  return (
    <div className={cx(styles.field, className)}>
      <label className={styles.fieldLabel} htmlFor={ids.controlId}>{label}</label>
      <Control
        id={ids.controlId}
        className={cx(styles.control, error && styles.controlInvalid)}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(hint, error, ids)}
        {...rest}
      />
      {hint && <span id={ids.hintId} className={styles.fieldHint}>{hint}</span>}
      {error && <span id={ids.errorId} className={styles.fieldError} role="alert">{error}</span>}
    </div>
  );
}

/** Ô mật khẩu có nút Hiện/Ẩn (mock M1). Nhãn đọc màn hình đổi theo trạng thái, chữ thấy được nằm trong nhãn. */
export function PasswordField({ label, hint, error, id, className, ...rest }) {
  const ids = useFieldIds(id);
  const [shown, setShown] = useState(false);
  const ToggleIcon = shown ? EyeOff : Eye;
  return (
    <div className={cx(styles.field, className)}>
      <label className={styles.fieldLabel} htmlFor={ids.controlId}>{label}</label>
      <div className={styles.controlWrap}>
        <input
          id={ids.controlId}
          type={shown ? 'text' : 'password'}
          className={cx(styles.control, styles.controlWithAction, error && styles.controlInvalid)}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(hint, error, ids)}
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          {...rest}
        />
        <button
          type="button"
          className={styles.controlAction}
          aria-controls={ids.controlId}
          aria-label={shown ? S.common.hidePassword : S.common.showPassword}
          onClick={() => setShown((value) => !value)}
        >
          <ToggleIcon size={16} aria-hidden="true" />
          {shown ? S.common.hide : S.common.show}
        </button>
      </div>
      {hint && <span id={ids.hintId} className={styles.fieldHint}>{hint}</span>}
      {error && <span id={ids.errorId} className={styles.fieldError} role="alert">{error}</span>}
    </div>
  );
}

export function SelectField({ label, hint, error, id, options, className, ...rest }) {
  const ids = useFieldIds(id);
  return (
    <div className={cx(styles.field, className)}>
      <label className={styles.fieldLabel} htmlFor={ids.controlId}>{label}</label>
      <select id={ids.controlId} className={cx(styles.control, error && styles.controlInvalid)} aria-describedby={describedBy(hint, error, ids)} {...rest}>
        {options.map((option) => (
          <option key={option.value} value={option.value} disabled={option.disabled}>{option.label}</option>
        ))}
      </select>
      {hint && <span id={ids.hintId} className={styles.fieldHint}>{hint}</span>}
      {error && <span id={ids.errorId} className={styles.fieldError} role="alert">{error}</span>}
    </div>
  );
}

export function EmptyState({ icon, title, body, action, className }) {
  const Icon = icon;
  return (
    <div className={cx(styles.empty, className)} role="status">
      {Icon && <Icon size={36} strokeWidth={1.6} className={styles.emptyIcon} aria-hidden="true" />}
      <strong className={styles.emptyTitle}>{title}</strong>
      {body && <p className={styles.emptyBody}>{body}</p>}
      {action}
    </div>
  );
}

export function Skeleton({ width = '100%', height = 14, className }) {
  return <span className={cx(styles.skeleton, className)} style={{ width, height }} aria-hidden="true" />;
}

/** Khung xương khi tải: vài dòng, có nhãn cho trình đọc màn hình. */
export function SkeletonBlock({ lines = 3, label = S.common.loading }) {
  return (
    <div className={styles.skeletonStack} role="status" aria-live="polite">
      <span className="ws-visually-hidden">{label}</span>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} width={i === lines - 1 ? '60%' : '100%'} />
      ))}
    </div>
  );
}

/** Banner lỗi tải dữ liệu: thông báo dễ hiểu + mã lỗi (request_id) + Thử lại. Không tự ẩn. */
export function ErrorBanner({ error, message, onRetry, tone = 'danger' }) {
  const text = message || userMessage(error);
  const BannerIcon = tone === 'success' ? CheckCircle2 : AlertCircle;
  return (
    <div className={cx(styles.banner, tone === 'warning' && styles.bannerWarning, tone === 'success' && styles.bannerSuccess)} role={tone === 'success' ? 'status' : 'alert'}>
      <BannerIcon size={18} aria-hidden="true" style={{ flex: 'none', marginTop: 1 }} />
      <div className={styles.bannerBody}>
        <span>{text}</span>
        {error?.requestId && <span className={styles.bannerMeta}>{S.errors.requestId}: <span className="ws-mono">{error.requestId}</span></span>}
      </div>
      {onRetry && <Button size="small" icon={RotateCw} onClick={onRetry}>{S.common.retry}</Button>}
    </div>
  );
}

/** Chân danh sách phân trang (Q26): "Đang hiển thị x / y", Tải thêm, đang tải, đã hết, lỗi. */
export function LoadMore({ count, total, noun, pageSize, loading, done, error, onLoadMore }) {
  return (
    <div className={styles.loadMore}>
      <span className={styles.loadMoreText} aria-live="polite">{S.common.shown(count, total, noun)}</span>
      {error && <span className={styles.loadMoreError} role="alert">{userMessage(error)}</span>}
      {done ? (
        <span className={styles.loadMoreText}>{S.common.allShown}</span>
      ) : (
        <Button onClick={onLoadMore} loading={loading} loadingLabel={S.common.loading}>
          {error ? S.common.retry : S.common.loadMore(pageSize, noun)}
        </Button>
      )}
    </div>
  );
}

export function PageHeader({ title, description, actions }) {
  return (
    <header className={styles.pageHeader}>
      <div className={styles.pageTitleWrap}>
        <h1 className={styles.pageTitle}>{title}</h1>
        {description && <p className={styles.pageDescription}>{description}</p>}
      </div>
      {actions && <div className={styles.pageActions}>{actions}</div>}
    </header>
  );
}
