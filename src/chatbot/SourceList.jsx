import { useEffect, useId, useState } from 'react';
import { createPortal } from 'react-dom';
import { useTranslation } from 'react-i18next';
import mdStyles from '../components/Markdown.module.css';
import { citationNumber } from '../components/markdownCitations.js';
import styles from './Chatbot.module.css';

// Chỉ nhận URL https do backend ký (Supabase Storage); bỏ mọi giá trị khác.
const isSafeUrl = (url) => typeof url === 'string' && url.startsWith('https://');

const pageLabel = (pages) => (pages ? ` · tr. ${pages}` : '');

const TIP_MAX_WIDTH = 220;

/**
 * Huy hiệu tròn thay cho [S1] trong câu trả lời. Di chuột, chạm hoặc Tab vào thì hiện
 * "tiêu đề · trang" của nguồn (từ event `sources`); lịch sử tải lại chưa có nguồn thì chỉ hiện số.
 */
export function Citation({ id, sources }) {
    const { t } = useTranslation();
    const [tip, setTip] = useState(null);
    const tipId = useId();
    const source = (sources || []).find((item) => item.source_id === id);
    const label = source
        ? [source.title, source.pages && t('chatbot.sourcePage', { pages: source.pages })].filter(Boolean).join(' · ')
        : t('chatbot.source', { id });

    // Chú thích gắn vào body (position: fixed) để không bị khung bảng hay khung tin nhắn cắt.
    const show = (event) => {
        const rect = event.currentTarget.getBoundingClientRect();
        const half = TIP_MAX_WIDTH / 2;
        const x = Math.min(Math.max(rect.left + rect.width / 2, half + 8), window.innerWidth - half - 8);
        setTip({ x, y: rect.top - 6 });
    };
    const hide = () => setTip(null);

    // Cuộn khung tin nhắn thì chú thích lệch chỗ: ẩn đi.
    useEffect(() => {
        if (!tip) return undefined;
        window.addEventListener('scroll', hide, true);
        return () => window.removeEventListener('scroll', hide, true);
    }, [tip]);

    return (
        <>
            <button
                type="button"
                className={mdStyles.cite}
                aria-label={`${t('chatbot.source', { id })}: ${label}`}
                aria-describedby={tip ? tipId : undefined}
                onMouseEnter={show}
                onMouseLeave={hide}
                onFocus={show}
                onBlur={hide}
                onKeyDown={(event) => event.key === 'Escape' && hide()}
            >
                {citationNumber(id)}
            </button>
            {tip && createPortal(
                <span id={tipId} className={styles.citeTip} role="tooltip" style={{ left: tip.x, top: tip.y, maxWidth: TIP_MAX_WIDTH }}>
                    {label}
                </span>,
                document.body,
            )}
        </>
    );
}

export default function SourceList({ sources }) {
    if (!Array.isArray(sources) || sources.length === 0) return null;
    return (
        <div className={styles.sourceList}>
            {sources.map((source) => {
                const images = (source.images || []).filter((image) => isSafeUrl(image.url));
                return (
                    <section className={styles.sourceItem} key={source.source_id}>
                        <p className={styles.sourceTitle}>
                            <span className={`${mdStyles.cite} ${styles.sourceChip}`} aria-label={source.source_id}>
                                {citationNumber(source.source_id)}
                            </span>
                            {source.title}{pageLabel(source.pages)}
                        </p>
                        {images.length > 0 && (
                            <div className={styles.sourceImages}>
                                {images.map((image) => (
                                    <a
                                        key={image.url}
                                        href={image.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        aria-label={`${source.title}, trang ${image.page ?? ''}`}
                                    >
                                        <img
                                            src={image.url}
                                            alt={`${source.title}${image.page ? `, trang ${image.page}` : ''}`}
                                            loading="lazy"
                                            referrerPolicy="no-referrer"
                                        />
                                    </a>
                                ))}
                            </div>
                        )}
                    </section>
                );
            })}
        </div>
    );
}
