// Dòng hoạt động AI trong bong bóng trả lời (mock W1/W2). Trạng thái và hiệu ứng: canvas v83, ghi chú W1.
// - live: thẻ mở, tiêu đề là bước đang chạy (aria-live). Chưa có event nào trong 1,5 giây: chữ cũ `fallbackText`.
// - answering (có chữ đầu tiên) / done / stopped: thu gọn thành một dòng, bấm để mở lại.
// - done có cảnh báo/lỗi, hoặc error: để mở sẵn.

import { useEffect, useId, useState } from 'react';
import { attempts, describeStep, openByDefault, strings, summarize } from './activityModel.js';
import styles from './Activity.module.css';

const FALLBACK_AFTER_MS = 1500;
const SHOW_TIMER_AFTER_MS = 3000;
const SLOW_AFTER_MS = 15000;

function useNow(active) {
    const [now, setNow] = useState(() => Date.now());
    useEffect(() => {
        if (!active) return undefined;
        const timer = setInterval(() => setNow(Date.now()), 500);
        return () => clearInterval(timer);
    }, [active]);
    return now;
}

const ICON = { done: '✓', warn: '!', retry: '↻', error: '!', skipped: '–' };

export default function ActivityTimeline({ activity, fallbackText }) {
    const { steps = [], phase = 'live', lang = 'en', startedAt, endedAt } = activity || {};
    const S = strings(lang);
    const listId = useId();
    const live = phase === 'live' || phase === 'answering';
    const now = useNow(live);
    const collapsible = phase !== 'live' && phase !== 'error';
    const [open, setOpen] = useState(null); // null = theo mặc định của pha
    const isOpen = !collapsible || (open ?? (phase === 'done' && openByDefault(steps)));

    if (phase === 'live' && steps.length === 0) {
        if (now - (startedAt ?? now) >= FALLBACK_AFTER_MS) {
            return <span className={styles.legacy}>{fallbackText}</span>;
        }
        return (
            <div className={styles.card} role="status" aria-live="polite">
                <div className={`${styles.summary} ${styles.live}`}><span className={styles.spin} aria-hidden="true" />{S.starting}</div>
            </div>
        );
    }
    if (steps.length === 0) return null;

    const summary = summarize(steps, phase, lang, (endedAt ?? now) - (startedAt ?? now));
    const counts = attempts(steps);
    const statusIcon = { ok: '✓', warn: '!', error: '!', muted: '–' }[summary.tone] || null;

    const list = (
        <ol className={styles.steps} id={listId}>
            {steps.map((item, index) => {
                const { label, detail, chips } = describeStep(item, lang, counts[index]);
                const running = item.state === 'running';
                const elapsed = running ? now - item.startedAt : 0;
                const crm = item.step === 'tool' && String(item.data?.tool || '').startsWith('crm_');
                return (
                    <li key={item.id} className={`${styles.step} ${styles[item.state] || ''}`}>
                        <span className={styles.icon} aria-hidden="true">{ICON[item.state] || ''}</span>
                        <div className={styles.body}>
                            <div className={styles.label}>
                                {label}
                                {elapsed >= SHOW_TIMER_AFTER_MS && <span className={styles.timer}>{` · ${S.seconds(Math.floor(elapsed / 1000))}`}</span>}
                            </div>
                            {detail && <div className={styles.detail}>{detail}</div>}
                            {elapsed >= SLOW_AFTER_MS && <div className={styles.slow}>{crm ? S.slowCrm : S.slow}</div>}
                            {chips.length > 0 && (
                                <div className={styles.chips}>
                                    {chips.map((chip) => (
                                        <span key={`${chip.kind}:${chip.text}`} className={`${styles.chip} ${styles[`chip_${chip.kind}`] || ''}`} title={chip.text}>
                                            {chip.text}
                                        </span>
                                    ))}
                                </div>
                            )}
                        </div>
                    </li>
                );
            })}
        </ol>
    );

    if (!collapsible) {
        return (
            <div className={styles.card}>
                <div className={`${styles.summary} ${styles.live}`} role="status" aria-live="polite">
                    {phase === 'live' && <span className={styles.spin} aria-hidden="true" />}
                    {phase === 'error' && <span className={`${styles.mark} ${styles.mark_error}`} aria-hidden="true">!</span>}
                    {summary.text}
                </div>
                {list}
            </div>
        );
    }

    return (
        <div className={styles.inline}>
            <button
                type="button"
                className={styles.summary}
                aria-expanded={isOpen}
                aria-controls={listId}
                onClick={() => setOpen(!isOpen)}
            >
                {phase === 'answering'
                    ? <span className={styles.spin} aria-hidden="true" />
                    : statusIcon && <span className={`${styles.mark} ${styles[`mark_${summary.tone}`] || ''}`} aria-hidden="true">{statusIcon}</span>}
                <span className={styles.summaryText}>{summary.text}</span>
                <span className={`${styles.chev} ${isOpen ? styles.chevUp : ''}`} aria-hidden="true">▾</span>
            </button>
            <div className={`${styles.fold} ${isOpen ? '' : styles.closed}`} aria-hidden={!isOpen}>
                <div>{list}</div>
            </div>
        </div>
    );
}
