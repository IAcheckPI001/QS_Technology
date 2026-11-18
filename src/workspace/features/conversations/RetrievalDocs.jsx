// Nội dung "Tài liệu chatbot đã dùng" của một lượt (Q23): ô tóm tắt, thẻ đoạn (thứ hạng, độ khớp,
// chủ đề, nguồn, nội dung 3 dòng + xem đầy đủ), chi tiết kỹ thuật của lần tra cứu.
// Nguồn tài liệu và mục chỉ có sau W1/B5 (FRONTEND_REQUIREMENTS 19.8); chưa có thì không hiện dòng nguồn.

import { useState } from 'react';
import { Badge } from '../../components/ui.jsx';
import { S } from '../../strings.vi.js';
import { formatDuration, formatScore } from '../../utils/format.js';
import styles from './detail.module.css';

function topicLabel(scopes = []) {
  return scopes.map((scope) => S.conv.topic[scope] || scope).join(', ');
}

function sourceLine(chunk) {
  const parts = [chunk.doc_title || chunk.doc_id, (chunk.section_path || []).join(' › ') || chunk.section_title].filter(Boolean);
  return parts.join(' · ');
}

export default function RetrievalDocs({ snapshot, cited = new Set() }) {
  const [open, setOpen] = useState({});
  const [techOpen, setTechOpen] = useState(false);
  const chunks = snapshot.chunks || [];
  const status = snapshot.retrieval_status;
  const top = chunks.length ? Math.max(...chunks.map((chunk) => chunk.score ?? 0)) : null;

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
          <strong>{formatScore(top)}</strong>
        </div>
      </div>

      {chunks.map((chunk) => {
        const key = chunk.chunk_id || chunk.rank;
        const expanded = Boolean(open[key]);
        const source = sourceLine(chunk);
        const topic = topicLabel(chunk.scopes);
        const width = `${Math.round(Math.min(Math.max(chunk.score ?? 0, 0), 1) * 100)}%`;
        return (
          <article key={key} className={styles.chunk} aria-label={`#${chunk.rank}`}>
            <div className={styles.chunkHead}>
              <strong>#{chunk.rank}</strong>
              <span className={styles.score}>
                {S.conv.docsScore} <b>{formatScore(chunk.score)}</b>
                <span className={styles.meter} aria-hidden="true"><span style={{ width }} /></span>
              </span>
              {topic && <Badge>{topic}</Badge>}
              {chunk.source_id && cited.has(chunk.source_id) && <Badge tone="brand">{S.conv.src.cited(chunk.source_id)}</Badge>}
            </div>
            {source && <span className={styles.chunkSource}>{source}</span>}
            <div className={expanded ? styles.chunkBody : `${styles.chunkBody} ${styles.clamp}`}>{chunk.content}</div>
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
