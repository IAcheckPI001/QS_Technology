// Nội dung khung "Nguồn câu trả lời · lượt N" (Q28, mock version 49, FRONTEND_REQUIREMENTS 19.14):
// tài liệu, dữ liệu CRM, cả hai, trả lời thẳng, không tìm thấy, tra cứu lỗi, không có nguồn.
// `data` là response của GET /retrieval?history_id (B5).

import { Link } from 'react-router-dom';
import { S } from '../../strings.vi.js';
import RetrievalDocs from './RetrievalDocs.jsx';
import { citedSources, crmCalls, noneReason, sourceKind } from './sources.js';
import { analyzeTools } from './toolErrors.js';
import styles from './detail.module.css';

function Box({ tone, title, children }) {
  return (
    <div className={`${styles.srcBox} ${styles[`srcBox_${tone}`]}`} role="status">
      <strong>{title}</strong>
      {children}
    </div>
  );
}

function CrmTools({ sources, agentSteps, both, traceTo }) {
  const { rows, verdict } = analyzeTools(agentSteps, sources);
  return (
    <section className={styles.srcSection} aria-label={S.conv.src.crmHeading}>
      <h3 className={styles.srcHeading}>{S.conv.src.crmHeading}</h3>
      <p className={styles.srcText}>{both ? S.conv.src.crmBoth : S.conv.src.crmOnly} {S.conv.src.crmCalls(crmCalls(sources))}</p>
      {verdict && (
        <div className={`${styles.verdict} ${styles[`verdict_${verdict.tone}`]}`} role="status">
          <strong>{verdict.title}</strong>
          {verdict.detail && <span>{verdict.detail}</span>}
        </div>
      )}
      <table className={styles.tools}>
        <thead>
          <tr><th scope="col">{S.conv.src.colTool}</th><th scope="col">{S.conv.src.colResult}</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.name}>
              <td>{row.label}</td>
              <td>
                <span className={row.failed && !row.ok ? styles.resultBad : row.failed ? styles.resultMixed : styles.resultOk}>{row.result}</span>
                {row.reasons.length > 0 && (
                  <ul className={styles.reasons}>
                    {row.reasons.map((reason) => (
                      <li key={reason.code}>
                        <span>{reason.text}{S.conv.src.reasonCount(reason.count)}</span>
                        <span className={styles.reasonWho}>{reason.who}</span>
                        <span className={`ws-mono ${styles.reasonCode}`}>{reason.code}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Link to={traceTo} className={styles.srcLink}>{S.conv.viewTrace}</Link>
    </section>
  );
}

export default function SourcePanel({ data, answer, traceTo }) {
  const kind = sourceKind(data.sources, data.turn_status);
  const sources = data.sources || {};
  const hasDocs = kind === 'docs' || (kind === 'both' && (data.chunks || []).length > 0);

  return (
    <div className={styles.docs}>
      {hasDocs && (
        <section className={styles.srcSection} aria-label={S.conv.src.docsHeading}>
          <h3 className={styles.srcHeading}>{S.conv.src.docsHeading}</h3>
          {data.retrieval_status === 'partial_error' && <p className={styles.srcWarn}>{S.conv.src.partialWarn}</p>}
          <RetrievalDocs snapshot={data} cited={citedSources(answer)} />
        </section>
      )}
      {(kind === 'crm' || kind === 'both') && (
        <CrmTools sources={sources} agentSteps={data.agent_steps} both={kind === 'both'} traceTo={traceTo} />
      )}
      {kind === 'direct' && (
        <Box tone="neutral" title={S.conv.src.directTitle}><span>{S.conv.src.directBody}</span></Box>
      )}
      {kind === 'nohits' && (
        <Box tone="warning" title={S.conv.src.nohitsTitle}>
          {data.query && <span>{S.conv.src.searched(data.query)}</span>}
          <span>{S.conv.src.nohitsBody}</span>
        </Box>
      )}
      {kind === 'rerr' && (
        <Box tone="danger" title={S.conv.src.rerrTitle}>
          <span>{S.conv.src.rerrBody}</span>
          <Link to={traceTo} className={styles.srcLink}>{S.conv.viewTrace}</Link>
        </Box>
      )}
      {(kind === 'none' || kind === null) && (
        <Box tone="neutral" title={S.conv.src.noneTitle}><span>{noneReason(data.turn_status)}</span></Box>
      )}
    </div>
  );
}
