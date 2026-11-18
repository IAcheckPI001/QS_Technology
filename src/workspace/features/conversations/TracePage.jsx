// Diễn biến xử lý của một lượt (mock Trace / TraceCompleted / TraceBlocked / TraceCancelled, điện thoại M4).
// Đọc GET /chatbot/sessions/{id}/trace?history_id=. Không có trace (404 trace_not_found) là trường hợp
// thường gặp (CHAT_TRACE_PERSIST tắt hoặc lượt cũ), hiện trạng thái rỗng, không báo lỗi.

import { useMemo, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { AlertCircle, AlertTriangle, ChevronLeft, PauseCircle, ShieldX, Workflow } from 'lucide-react';
import { conversationsApi } from '../../api/conversations.js';
import { Badge, Card, EmptyState, ErrorBanner, SkeletonBlock } from '../../components/ui.jsx';
import { useResource } from '../../hooks/useResource.js';
import { S } from '../../strings.vi.js';
import { formatDayTime, formatDuration, formatDurationShort, formatNumber } from '../../utils/format.js';
import { channelLabel } from './status.js';
import { describeTrace, isFailed, spanErrorInfo, spanLabel, spanResultLabel, spanStatusTone } from './traceModel.js';
import styles from './trace.module.css';

const KIND_COLOR = { server: '#5b6372', db: '#8c6d1f', stage: '#5c3810', internal: '#3b4250', llm: '#6b3fc4', tool: '#1d7a4d', http: '#a35c00' };

export default function TracePage() {
  const { sessionId, historyId } = useParams();
  const location = useLocation();
  const backTo = { pathname: `/conversations/${encodeURIComponent(sessionId)}`, state: location.state };
  const trace = useResource(({ signal }) => conversationsApi.trace(sessionId, historyId, { signal }), [sessionId, historyId]);

  let content;
  if (trace.loading && !trace.data) content = <Card className={styles.pad}><SkeletonBlock lines={8} /></Card>;
  else if (trace.error?.kind === 'not_found') {
    content = (
      <>
        <h1 className={styles.title}>{S.trace.title}</h1>
        <Card><EmptyState icon={Workflow} title={S.trace.noneTitle} body={S.trace.noneBody} /></Card>
      </>
    );
  } else if (trace.error) {
    content = (
      <>
        <h1 className={styles.title}>{S.trace.title}</h1>
        <ErrorBanner error={trace.error} onRetry={trace.reload} />
      </>
    );
  } else content = <TraceView trace={trace.data} />;

  return (
    <div className={styles.page}>
      <Link to={backTo} className={styles.back}>
        <ChevronLeft size={16} aria-hidden="true" />
        {S.trace.back}
      </Link>
      {content}
    </div>
  );
}

const OUTCOME_LABEL = (trace, kind) => {
  if (kind === 'error') return S.trace.outcomeError;
  return S.trace.outcome[trace.outcome] || trace.outcome;
};

// Tiêu đề theo trạng thái lượt như ở màn hội thoại ("lượt hoàn tất", "lượt bị chặn"…).
const TITLE_STATUS = { ok: 'completed', tool_warning: 'completed', error: 'error', blocked: 'blocked', cancelled: 'cancelled' };

function TraceView({ trace }) {
  const info = useMemo(() => describeTrace(trace), [trace]);
  const [selected, setSelected] = useState(info.focus?.span_id || null);
  const [onlyErrors, setOnlyErrors] = useState(false);
  const rootSpan = info.rows[0]?.span;
  const rootAttrs = rootSpan?.attributes || {};
  const total = Math.max(trace.duration_ms || 0, ...info.rows.map((row) => (row.span.start_ms || 0) + (row.span.duration_ms || 0)), 1);
  const summary = trace.summary || {};
  const label = OUTCOME_LABEL(trace, info.kind);
  const flow = S.trace.flow[rootAttrs.flow] || '';
  const rows = onlyErrors ? info.rows.filter((row) => isFailed(row.span.status) || row.span.status === 'cancelled') : info.rows;
  const current = info.rows.find((row) => row.span.span_id === selected)?.span || null;

  const tiles = [
    { label: S.trace.sumResult, value: label, tone: info.kind },
    { label: S.trace.sumDuration, value: formatDuration(trace.duration_ms), note: rootAttrs.first_delta_ms ? S.trace.sumFirstDelta(formatDuration(rootAttrs.first_delta_ms)) : '' },
    { label: S.trace.sumLlm, value: formatNumber(summary.llm_calls) },
  ];
  if (summary.tool_calls) tiles.push({ label: S.trace.sumTools, value: formatNumber(summary.tool_calls), note: summary.failed_tool_calls ? S.trace.sumToolsFailed(summary.failed_tool_calls) : '' });
  if (summary.error_spans) tiles.push({ label: S.trace.sumErrors, value: formatNumber(summary.error_spans), note: S.trace.sumErrorsRoot(summary.root_error_spans || 0) });
  if (summary.input_tokens || summary.output_tokens) {
    tiles.push({ label: S.trace.sumTokens, value: `${formatNumber(summary.input_tokens)} / ${formatNumber(summary.output_tokens)}`, note: S.trace.sumTokensNote });
  }

  return (
    <>
      <header className={styles.header}>
        <h1 className={styles.title}>{S.trace.titleFor(S.status[TITLE_STATUS[info.kind]] || label)}</h1>
        <span className={styles.sub}>{[channelLabel(trace.channel), flow, formatDayTime(trace.created_at)].filter(Boolean).join(' · ')}</span>
      </header>

      <Banner info={info} />

      <section aria-label={S.trace.sumResult} className={styles.tiles}>
        {tiles.map((tile) => (
          <Card key={tile.label} className={styles.tile}>
            <span className={styles.tileLabel}>{tile.label}</span>
            <strong className={`${styles.tileValue} ${styles[`tone_${tile.tone}`] || ''}`}>{tile.value}</strong>
            {tile.note && <span className={styles.tileNote}>{tile.note}</span>}
          </Card>
        ))}
      </section>

      <Card className={styles.steps} aria-labelledby="steps-title">
        <div className={styles.stepsHead}>
          <h2 id="steps-title" className={styles.h2}>{S.trace.stepsTitle}</h2>
          <label className={styles.toggle}>
            <input type="checkbox" checked={onlyErrors} onChange={(event) => setOnlyErrors(event.target.checked)} />
            {S.trace.onlyErrors}
          </label>
        </div>
        {summary.dropped_spans > 0 && <p className={styles.dropped}>{S.trace.dropped(summary.dropped_spans)}</p>}
        <div className={styles.grid}>
          <div className={`${styles.row} ${styles.rowHead}`} aria-hidden="true">
            <span>{S.trace.colStep}</span>
            <span>{S.trace.colTime(formatDuration(total))}</span>
            <span className={styles.right}>{S.trace.colDuration}</span>
            <span>{S.trace.colResult}</span>
          </div>
          {rows.length === 0 && <p className={styles.empty}>{S.trace.noErrorSteps}</p>}
          <ol className={styles.list}>
          {rows.map(({ span, depth }) => {
            const failed = isFailed(span.status);
            const start = ((span.start_ms || 0) / total) * 100;
            const width = Math.max(((span.duration_ms || 0) / total) * 100, 0.5);
            const isSelected = span.span_id === selected;
            return (
              <li key={span.span_id}>
              <button
                type="button"
                className={`${styles.row} ${failed ? styles.rowFailed : ''} ${isSelected ? styles.rowSelected : ''}`}
                aria-pressed={isSelected}
                onClick={() => setSelected(span.span_id)}
              >
                <span className={styles.stepName} style={{ paddingLeft: depth * 18 }}>
                  <span className={styles.stepLabel}>{spanLabel(span)}</span>
                  <span className="ws-mono">{span.name}</span>
                </span>
                <span className={styles.track} aria-hidden="true">
                  <span style={{ left: `${start.toFixed(2)}%`, width: `${width.toFixed(2)}%`, background: failed ? 'var(--ws-danger-solid)' : KIND_COLOR[span.kind] || '#5b6372' }} />
                </span>
                <span className={`ws-mono ${styles.right}`}>{formatDurationShort(span.duration_ms)}</span>
                <span><Badge tone={spanStatusTone(span.status)}>{spanResultLabel(span)}</Badge></span>
              </button>
              </li>
            );
          })}
          </ol>
        </div>
      </Card>

      <Card className={styles.detail} aria-live="polite">
        {current ? (
          <>
            <h2 className={styles.h2}>{S.trace.detailTitle(spanLabel(current), spanResultLabel(current))}</h2>
            {spanErrorInfo(current) && (
              <p className={styles.explain}>
                {spanErrorInfo(current).text} <span className={styles.explainWho}>{spanErrorInfo(current).who}</span>
              </p>
            )}
            <details className={styles.attrs} open>
              <summary>{S.trace.detailTech}</summary>
              <dl className="ws-mono">
                <div><dt>span</dt><dd>{current.name}</dd></div>
                <div><dt>status</dt><dd>{current.status}</dd></div>
                <div><dt>duration_ms</dt><dd>{current.duration_ms ?? '—'}</dd></div>
                {Object.entries(current.attributes || {}).map(([key, value]) => (
                  <div key={key}><dt>{key}</dt><dd>{Array.isArray(value) ? `[${value.join(', ')}]` : String(value)}</dd></div>
                ))}
              </dl>
            </details>
          </>
        ) : (
          <p className={styles.hint}>{S.trace.detailHint}</p>
        )}
        <p className={styles.privacy}>{S.trace.privacy}</p>
      </Card>
    </>
  );
}

const BANNER = {
  error: { icon: AlertCircle, cls: 'bannerError', role: 'alert' },
  blocked: { icon: ShieldX, cls: 'bannerWarn', role: 'status' },
  cancelled: { icon: PauseCircle, cls: 'bannerNeutral', role: 'status' },
  tool_warning: { icon: AlertTriangle, cls: 'bannerWarn', role: 'status' },
};

function Banner({ info }) {
  const style = BANNER[info.kind];
  if (!style) return null;
  const Icon = style.icon;
  return (
    <section role={style.role} className={`${styles.banner} ${styles[style.cls]}`}>
      <Icon size={22} aria-hidden="true" className={styles.bannerIcon} />
      <div className={styles.bannerBody}>
        <strong>{info.title}</strong>
        {info.body && <span>{info.body}</span>}
        {info.items?.length > 0 && (
          <ul>
            {info.items.map((item) => <li key={item.label}>{S.trace.toolErrorItem(item.label, item.count)}</li>)}
          </ul>
        )}
      </div>
    </section>
  );
}
