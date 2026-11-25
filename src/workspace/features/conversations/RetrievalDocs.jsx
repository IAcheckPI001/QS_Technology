// Nội dung "Tài liệu chatbot đã dùng" của một lượt (Q23): ô tóm tắt, thẻ đoạn (thứ hạng, độ khớp,
// chủ đề, nguồn, nội dung 3 dòng + xem đầy đủ), chi tiết kỹ thuật của lần tra cứu.
// Nguồn tài liệu và mục chỉ có sau W1/B5 (FRONTEND_REQUIREMENTS 19.8); chưa có thì không hiện dòng nguồn.

// Nội dung đoạn hiện dạng Markdown (bảng, danh sách). Bấm huy hiệu trích dẫn ở câu trả lời: `focus`
// ({ id: 'S1', n }) mở và cuộn tới đoạn có source_id đó; n đổi mỗi lần bấm để bấm lại vẫn cuộn.

import { useEffect, useMemo, useRef, useState } from 'react';
import Markdown from '../../../components/Markdown.jsx';
import { Badge } from '../../components/ui.jsx';
import { S } from '../../strings.vi.js';
import { formatDuration, formatScore, formatSimilarity } from '../../utils/format.js';
import { chunkPages } from './sources.js';
import styles from './detail.module.css';

function topicLabel(scopes = []) {
  return scopes.map((scope) => S.conv.topic[scope] || scope).join(', ');
}

function sourceLine(chunk) {
  const pages = chunkPages(chunk);
  const parts = [
    chunk.doc_title || chunk.doc_id,
    (chunk.section_path || []).join(' › ') || chunk.section_title,
    pages && S.conv.src.page(pages),
  ].filter(Boolean);
  return parts.join(' · ');
}

export default function RetrievalDocs({ snapshot, cited = new Set(), focus = null }) {
  const [open, setOpen] = useState({});
  const [techOpen, setTechOpen] = useState(false);
  const focusRef = useRef(null);
  const chunks = useMemo(() => snapshot.chunks || [], [snapshot.chunks]);

  useEffect(() => {
    if (!focus) return;
    const target = chunks.find((chunk) => chunk.source_id === focus.id);
    if (!target) return;
    setOpen((prev) => ({ ...prev, [target.chunk_id || target.rank]: true }));
    // Chờ đoạn mở ra rồi mới cuộn.
    requestAnimationFrame(() => focusRef.current?.scrollIntoView?.({ block: 'start', behavior: 'smooth' }));
    focusRef.current?.focus({ preventScroll: true });
  }, [focus, chunks]);
  const status = snapshot.retrieval_status;
  // Độ khớp thang 10 từ độ giống cosine (WU-11, WU-17 đợt 2); lượt cũ không lưu `similarity` thì không hiện điểm.
  const similarities = chunks.map((chunk) => chunk.similarity).filter((value) => typeof value === 'number');
  const top = similarities.length ? Math.max(...similarities) : null;

  return (
    <div className={styles.docs}>
      <div className={styles.docStats}>
        <div className={styles.docStat}>
          <span>{S.conv.docsResult}</span>
          <strong className={status === 'ok' ? styles.good : undefined}>{S.conv.retrieval[status] || (chunks.length ? S.conv.retrieval.ok : '—')}</strong>
        </div>
        <div className={styles.docStat}>
          <span>{S.conv.docsCount}</span>
          <strong>{S.conv.docsCountValue(chunks.length)}</strong>
        </div>
        <div className={styles.docStat}>
          <span>{S.conv.docsTop}</span>
          <strong>{formatSimilarity(top)}</strong>
        </div>
      </div>

      {chunks.map((chunk) => {
        const key = chunk.chunk_id || chunk.rank;
        const expanded = Boolean(open[key]);
        const source = sourceLine(chunk);
        const topic = topicLabel(chunk.scopes);
        const hasScore = typeof chunk.similarity === 'number';
        const width = `${Math.round(Math.min(Math.max(chunk.similarity ?? 0, 0), 1) * 100)}%`;
        const images = (chunk.images || []).filter((image) => typeof image.url === 'string' && image.url.startsWith('https://'));
        const focused = Boolean(focus && chunk.source_id === focus.id);
        return (
          <article
            key={key}
            ref={focused ? focusRef : undefined}
            className={focused ? `${styles.chunk} ${styles.chunkFocus}` : styles.chunk}
            aria-label={chunk.source_id ? `#${chunk.rank} · ${chunk.source_id}` : `#${chunk.rank}`}
            data-source-id={chunk.source_id || undefined}
            tabIndex={focused ? -1 : undefined}
          >
            <div className={styles.chunkHead}>
              <strong>#{chunk.rank}</strong>
              {hasScore && (
                <span className={styles.score} title={S.conv.docsRankScore(formatScore(chunk.score))}>
                  {S.conv.docsScore} <b>{formatSimilarity(chunk.similarity)}</b>
                  <span className={styles.meter} aria-hidden="true"><span style={{ width }} /></span>
                </span>
              )}
              {topic && <Badge>{topic}</Badge>}
              {chunk.source_id && cited.has(chunk.source_id) && <Badge tone="brand">{S.conv.src.cited(chunk.source_id)}</Badge>}
            </div>
            {source && <span className={styles.chunkSource}>{source}</span>}
            <Markdown text={chunk.content} className={expanded ? styles.chunkBody : `${styles.chunkBody} ${styles.clamp}`} />
            {images.length > 0 && (
              <div className={styles.chunkImages}>
                {images.map((image) => {
                  const alt = S.conv.src.imageAlt(chunk.section_title || chunk.doc_id || '', image.printed_page ?? image.page);
                  return (
                    <a key={image.url} href={image.url} target="_blank" rel="noopener noreferrer" aria-label={alt}>
                      <img src={image.url} alt={alt} loading="lazy" referrerPolicy="no-referrer" />
                    </a>
                  );
                })}
              </div>
            )}
            <button type="button" className={styles.link} aria-expanded={expanded} onClick={() => setOpen((prev) => ({ ...prev, [key]: !expanded }))}>
              {expanded ? S.conv.docsLess : S.conv.docsMore}
            </button>
          </article>
        );
      })}

      <button type="button" className={`${styles.link} ${styles.muted}`} aria-expanded={techOpen} onClick={() => setTechOpen((value) => !value)}>
        {techOpen ? S.conv.docsTechHide : S.conv.docsTech}
      </button>
      {techOpen && (
        <div className={styles.tech}>
          <span>{S.conv.docsLatency}<b>{formatDuration(snapshot.latency_ms)}</b></span>
          <span>{S.conv.docsStatusRaw}<b className="ws-mono">{status || '—'}</b></span>
          {snapshot.model && <span>{S.conv.techModel}<b>{snapshot.model}</b></span>}
        </div>
      )}
    </div>
  );
}
