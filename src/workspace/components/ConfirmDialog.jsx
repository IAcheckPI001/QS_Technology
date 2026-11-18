// Hộp xác nhận (18.3): nêu hậu quả; tuỳ chọn bắt gõ lại tên (thao tác không hoàn tác, Q27) và
// bắt nhập lý do (vd. Tắt khỏi chatbot). onConfirm có thể async: nút khoá trong lúc chờ.

import { useEffect, useState } from 'react';
import { S } from '../strings.vi.js';
import Modal from './Modal.jsx';
import { Button, TextField } from './ui.jsx';
import styles from './Overlay.module.css';

export default function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel,
  cancelLabel = S.common.cancel,
  tone = 'danger',
  requireText,
  requireReason,
  reasonPlaceholder,
  onConfirm,
  onCancel,
}) {
  const [typed, setTyped] = useState('');
  const [reason, setReason] = useState('');
  const [reasonError, setReasonError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (open) {
      setTyped('');
      setReason('');
      setReasonError('');
      setBusy(false);
    }
  }, [open]);

  const blocked = Boolean(requireText) && typed.trim() !== requireText;

  const confirm = async () => {
    if (blocked || busy) return;
    if (requireReason && !reason.trim()) {
      setReasonError(S.common.reasonRequired);
      return;
    }
    setBusy(true);
    try {
      await onConfirm?.(reason.trim());
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal
      open={open}
      onClose={busy ? undefined : onCancel}
      title={title}
      role="alertdialog"
      showClose={false}
      footer={(
        <>
          <Button onClick={onCancel} disabled={busy} data-autofocus={!requireText && !requireReason ? true : undefined}>{cancelLabel}</Button>
          <Button variant={tone === 'danger' ? 'danger' : tone === 'approve' ? 'approve' : 'primary'} onClick={confirm} disabled={blocked} loading={busy}>
            {confirmLabel}
          </Button>
        </>
      )}
    >
      {body && <p>{body}</p>}
      {requireReason && (
        <TextField
          label={S.common.reasonLabel}
          value={reason}
          placeholder={reasonPlaceholder}
          error={reasonError}
          onChange={(event) => {
            setReason(event.target.value);
            setReasonError('');
          }}
          data-autofocus
        />
      )}
      {requireText && (
        <TextField
          label={<>{S.common.typePrefix} <span className={styles.expect}>{requireText}</span> {S.common.typeToConfirm}</>}
          value={typed}
          autoComplete="off"
          spellCheck={false}
          className={styles.confirmInput}
          onChange={(event) => setTyped(event.target.value)}
          data-autofocus={requireReason ? undefined : true}
        />
      )}
    </Modal>
  );
}
