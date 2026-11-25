// Nội dung khung "Nguồn câu trả lời · lượt N" (Q28, mock version 49, FRONTEND_REQUIREMENTS 19.14):
// tài liệu, dữ liệu CRM, cả hai, trả lời thẳng, không tìm thấy, tra cứu lỗi, không có nguồn.
// `data` là response của GET /retrieval?history_id (B5).

// Lượt lỗi: đọc diễn biến (trace) của lượt để nói nguyên nhân bằng lời dễ hiểu (cùng câu với màn Diễn biến).

import { Link } from 'react-router-dom';
import { conversationsApi } from '../../api/conversations.js';
import { useResource } from '../../hooks/useResource.js';
import { S } from '../../strings.vi.js';
import RetrievalDocs from './RetrievalDocs.jsx';
import { citedSources, crmCalls, noneReason, sourceKind } from './sources.js';
import { analyzeTools } from './toolErrors.js';
import { describeTrace } from './traceModel.js';
import styles from './detail.module.css';

async function traceOrNull(promise) {
  try {
    return await promise;
  } catch (error) {
    if (error?.kind === 'not_found') return null; // lượt không lưu trace
    throw error;
  }
}

/** Hộp lỗi của lượt: nguyên nhân lấy từ trace nếu lượt có lưu; không có thì nói rõ là không biết. */
function ErrorReason({ sessionId, historyId, hasTrace, traceTo }) {
  const trace = useResource(
    ({ signal }) => (hasTrace === false ? Promise.resolve(null) : traceOrNull(conversationsApi.trace(sessionId, historyId, { signal }))),
    [sessionId, historyId, hasTrace],
  );
  const info = trace.data ? describeTrace(trace.data) : null;
  const known = info && info.kind === 'error';
  const code = known ? info.focus?.attributes?.provider_error_code || info.focus?.attributes?.error_code : null;
  return (
    <Box tone="danger" title={known ? info.title : S.conv.src.errTitle}>
      {trace.loading && <span>{S.conv.src.errLoading}</span>}
      {!trace.loading && known && <span>{info.body}</span>}
      {!trace.loading && !known && <span>{trace.data || trace.error ? noneReason('error') : S.conv.src.errNoTrace}</span>}
      {code && <span className={`ws-mono ${styles.errCode}`}>{code}</span>}
      {trace.data && <Link to={traceTo} className={styles.srcLink}>{S.conv.viewTrace}</Link>}
    </Box>
  );
}

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

export default function SourcePanel({ data, answer, traceTo, sessionId, hasTrace, focus }) {
  const kind = sourceKind(data.sources, data.turn_status);
  const sources = data.sources || {};
  const hasDocs = kind === 'docs' || (kind === 'both' && (data.chunks || []).length > 0);

  return (
    <div className={styles.docs}>
      {hasDocs && (
        <section className={styles.srcSection} aria-label={S.conv.src.docsHeading}>
          <h3 className={styles.srcHeading}>{S.conv.src.docsHeading}</h3>
          {data.retrieval_status === 'partial_error' && <p className={styles.srcWarn}>{S.conv.src.partialWarn}</p>}
          <RetrievalDocs snapshot={data} cited={citedSources(answer)} focus={focus} />
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
      {(kind === 'none' || kind === null) && data.turn_status === 'error' && (
        <ErrorReason sessionId={sessionId} historyId={data.history_id} hasTrace={hasTrace} traceTo={traceTo} />
      )}
      {(kind === 'none' || kind === null) && data.turn_status !== 'error' && (
        <Box tone="neutral" title={S.conv.src.noneTitle}><span>{noneReason(data.turn_status)}</span></Box>
      )}
    </div>
  );
}
