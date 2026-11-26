// Cửa sổ xem hình (mock 5b/5 v4): bấm ảnh của đoạn thì mở to, ‹ › hoặc phím ← → chuyển hình trong cùng đoạn,
// Esc đóng, "Mở trang này trong PDF" nhảy PDF tới trang của hình. Phím bắt trên chính lớp phủ, không nghe toàn trang.

import { useEffect, useRef } from 'react';
import { ChevronLeft, ChevronRight, FileText, X } from 'lucide-react';
import { S } from '../../strings.vi.js';
import styles from './documents.module.css';

export default function ImageViewer({ images, index, title, captions, onIndex, onClose, onOpenPage }) {
  const closeRef = useRef(null);
  const n = images.length;
  const image = images[index];

  useEffect(() => {
    const back = document.activeElement;
    closeRef.current?.focus();
    return () => back?.focus?.();
  }, []);

  const go = (step) => onIndex((index + step + n) % n);
  const onKey = (event) => {
    if (event.key === 'Escape') { event.preventDefault(); onClose(); }
    else if (event.key === 'ArrowLeft' && n > 1) { event.preventDefault(); go(-1); }
    else if (event.key === 'ArrowRight' && n > 1) { event.preventDefault(); go(1); }
  };
  const page = image.printed_page ?? image.page;
  // Có dòng "Figure N." thì làm tiêu đề, kèm tên đoạn ở dòng phụ; không có thì tên đoạn làm tiêu đề.
  const caption = captions[index] || title;
  const sub = captions[index] ? title : null;

  return (
    <div className={styles.viewer} role="dialog" aria-modal="true" aria-label={S.docs.viewer.label} onKeyDown={onKey}
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className={styles.viewerHead}>
        <div className={styles.viewerTitles}>
          <strong>{caption}</strong>
          <span>{[sub, page != null ? S.docs.printed(page) : null, `${index + 1} / ${n}`].filter(Boolean).join(' · ')}</span>
        </div>
        <div className={styles.viewerActions}>
          {image.page != null && (
            <button type="button" className={styles.viewerBtn} onClick={() => onOpenPage(image.page)}>
              <FileText size={16} aria-hidden="true" />{S.docs.viewer.openPage}
            </button>
          )}
          <button type="button" ref={closeRef} className={styles.viewerBtn} onClick={onClose} aria-label={S.docs.viewer.close}>
            <X size={16} aria-hidden="true" />{S.docs.viewer.closeShort}
          </button>
        </div>
      </div>
      <div className={styles.viewerStage}>
        {n > 1 && (
          <button type="button" className={styles.viewerNav} onClick={() => go(-1)} aria-label={S.docs.viewer.prev}>
            <ChevronLeft size={24} aria-hidden="true" />
          </button>
        )}
        <figure className={styles.viewerFigure}>
          <img src={image.url} alt={caption} referrerPolicy="no-referrer" />
        </figure>
        {n > 1 && (
          <button type="button" className={styles.viewerNav} onClick={() => go(1)} aria-label={S.docs.viewer.next}>
            <ChevronRight size={24} aria-hidden="true" />
          </button>
        )}
      </div>
      <p className={styles.viewerHint}>{n > 1 ? S.docs.viewer.hint : S.docs.viewer.hintOne}</p>
    </div>
  );
}
