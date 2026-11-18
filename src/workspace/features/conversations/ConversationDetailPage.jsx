// Chi tiết hội thoại (mock màn 3, điện thoại M3; Q23, Q26, Q28 version 49).
// - Trang vừa khít chiều cao màn hình; hai khung "Các lượt hỏi đáp" và "Nguồn câu trả lời" tự cuộn.
// - Mở ra hiện 20 lượt mới nhất, khung lượt cuộn sẵn tới cuối; "Tải 20 lượt cũ hơn" chèn lên đầu, giữ chỗ đang đọc.
// - Giờ hỏi = created_at − latency_ms (19.2 W3); thông số kỹ thuật nằm trong "Chi tiết kỹ thuật".
// - Tiêu đề = câu hỏi cuối, khớp danh sách.
// Nguồn câu trả lời: backend có B5 (lượt có `sources`) thì mỗi lượt có nhãn nguồn, bấm để xem ở khung phải
// (mặc định lượt mới nhất; điện thoại mở sheet). Backend cũ: chỉ tài liệu của lượt mới nhất có tra cứu.

import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { ChevronLeft, FileSearch, MessageSquareOff } from 'lucide-react';
import { conversationsApi, TURN_PAGE_SIZE } from '../../api/conversations.js';
import Highlight from '../../components/Highlight.jsx';
import Modal from '../../components/Modal.jsx';
import { Badge, Button, Card, EmptyState, ErrorBanner, SkeletonBlock } from '../../components/ui.jsx';
import { PHONE_QUERY, useMediaQuery } from '../../hooks/useMediaQuery.js';
import { useResource } from '../../hooks/useResource.js';
import { S } from '../../strings.vi.js';
import { askedAt, formatDuration, formatFullDateTime, formatNumber, formatTime, formatUsd, formatVnd, sameDay } from '../../utils/format.js';
import RetrievalDocs from './RetrievalDocs.jsx';
import SourcePanel from './SourcePanel.jsx';
import { sourceKind, sourceLabel, sourceTone } from './sources.js';
import { channelLabel, statusLabel, statusNote, statusTone } from './status.js';
import styles from './detail.module.css';

const STATUS_ORDER = ['completed', 'error', 'blocked', 'cancelled'];

async function ignoreNotFound(promise) {
  try {
    return await promise;
  } catch (error) {
    if (error?.kind === 'not_found') return null; // retrieval_not_found: hội thoại chưa có lượt nào tra cứu
    throw error;
  }
}

export default function ConversationDetailPage() {
  const { sessionId } = useParams();
  const location = useLocation();
  const backTo = `/conversations${location.state?.from || ''}`;
  const history = useResource(({ signal }) => conversationsApi.history(sessionId, { signal }), [sessionId]);
  const turns = useMemo(() => history.data?.messages || [], [history.data]);

  if (history.loading && !history.data) {
    return (
      <div className={styles.page}>
        <BackLink to={backTo} />
        <Card className={styles.pad}><SkeletonBlock lines={6} /></Card>
      </div>
    );
  }
  if (history.error) {
    return (
      <div className={styles.page}>
        <BackLink to={backTo} />
        {history.error.kind === 'not_found' ? (
          <Card><EmptyState icon={MessageSquareOff} title={S.conv.notFoundTitle} body={S.conv.notFoundBody} /></Card>
        ) : (
          <ErrorBanner error={history.error} onRetry={history.reload} />
        )}
      </div>
    );
  }

  // Mở từ dòng khớp tìm kiếm (B2): `?turn=` là lượt khớp, `?q=` là từ khoá để tô.
  const params = new URLSearchParams(location.search);
  const focusId = params.get('turn');
  const query = params.get('q') || '';
  return (
    <Detail
      key={`${sessionId}:${focusId || ''}`}
      sessionId={sessionId}
      turns={turns}
      backTo={backTo}
      from={location.state?.from}
      focusId={turns.some((turn) => turn.id === focusId) ? focusId : null}
      query={query}
    />
  );
}

function BackLink({ to }) {
  return (
    <Link to={to} className={styles.back}>
      <ChevronLeft size={16} aria-hidden="true" />
      {S.conv.back}
    </Link>
  );
}

const traceLink = (sessionId, turnId) => `/conversations/${encodeURIComponent(sessionId)}/turns/${encodeURIComponent(turnId)}/trace`;

function Detail({ sessionId, turns, backTo, from, focusId, query }) {
  const phone = useMediaQuery(PHONE_QUERY);
  // Lượt khớp nằm ngoài 20 lượt mới nhất: mở rộng phần đang hiện tới lượt đó.
  const focusIndex = focusId ? turns.findIndex((turn) => turn.id === focusId) : -1;
  const [visible, setVisible] = useState(() => Math.max(TURN_PAGE_SIZE, focusIndex >= 0 ? turns.length - focusIndex : 0));
  const [tech, setTech] = useState({});
  const [sheetOpen, setSheetOpen] = useState(false);
  const [pickedId, setPickedId] = useState(focusId);
  const scrollRef = useRef(null);
  const anchorRef = useRef(null);
  const docsRef = useRef(null);

  const first = turns[0];
  const last = turns[turns.length - 1];
  const hidden = Math.max(turns.length - visible, 0);
  const shown = turns.slice(hidden);
  // Backend có B5: mỗi lượt có `sources`.
  const perTurn = turns.some((turn) => turn.sources);
  const selectedId = perTurn ? pickedId || last?.id : null;

  // B5: nguồn của lượt đang chọn. Backend cũ: tài liệu của lượt mới nhất có tra cứu.
  const source = useResource(
    ({ signal }) =>
      perTurn
        ? conversationsApi.retrievalForTurn(sessionId, selectedId, { signal })
        : ignoreNotFound(conversationsApi.retrieval(sessionId, { signal })),
    [sessionId, perTurn, selectedId],
  );
  const data = source.data;
  const panelTurnId = perTurn ? selectedId : data?.history_id;
  const panelIndex = turns.findIndex((turn) => turn.id === panelTurnId);
  const panelTurn = panelIndex >= 0 ? turns[panelIndex] : null;
  const legacyCount = !perTurn ? data?.chunks?.length || 0 : 0;

  const counts = useMemo(() => {
    const map = {};
    turns.forEach((turn) => {
      map[turn.status] = (map[turn.status] || 0) + 1;
    });
    return STATUS_ORDER.filter((status) => map[status]).map((status) => ({ status, count: map[status] }));
  }, [turns]);

  // Mở trang: cuộn khung lượt tới cuối (lượt mới nhất). Tải lượt cũ hơn: giữ nguyên chỗ đang đọc.
  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    // Mở từ kết quả tìm kiếm (chưa bấm tải lượt cũ hơn): cuộn tới lượt khớp thay vì cuối khung.
    // Chạy lại (StrictMode) vẫn cho cùng kết quả.
    if (focusId && anchorRef.current === null) {
      const target = el.querySelector('[data-focus="true"]');
      if (target) {
        el.scrollTop += target.getBoundingClientRect().top - el.getBoundingClientRect().top - 12;
        return;
      }
    }
    if (anchorRef.current !== null) {
      el.scrollTop = el.scrollHeight - anchorRef.current;
      anchorRef.current = null;
    } else {
      el.scrollTop = el.scrollHeight;
    }
  }, [visible, focusId]);

  const loadOlder = () => {
    const el = scrollRef.current;
    if (el) anchorRef.current = el.scrollHeight - el.scrollTop;
    setVisible((value) => value + TURN_PAGE_SIZE);
  };

  const pick = (turnId) => {
    setPickedId(turnId);
    if (phone) setSheetOpen(true);
    else if (docsRef.current) docsRef.current.scrollTop = 0;
  };

  const timeRange = first
    ? sameDay(first.created_at, last.created_at)
      ? `${formatFullDateTime(askedAt(first) || first.created_at)} – ${formatTime(last.created_at)}`
      : `${formatFullDateTime(askedAt(first) || first.created_at)} – ${formatFullDateTime(last.created_at)}`
    : '';

  let panelBody;
  if (source.error) panelBody = <ErrorBanner error={source.error} onRetry={source.reload} />;
  else if (source.loading || (perTurn && data && data.history_id !== selectedId)) panelBody = <SkeletonBlock lines={4} />;
  else if (perTurn && data) panelBody = <SourcePanel data={data} answer={panelTurn?.answer} traceTo={traceLink(sessionId, data.history_id)} />;
  else if (!perTurn && legacyCount > 0) panelBody = <RetrievalDocs key={data.history_id} snapshot={data} />;
  else panelBody = <EmptyState icon={FileSearch} title={S.conv.docsEmptyTitle} body={S.conv.docsEmptyBody} />;

  const panelTitle = panelTurn ? (perTurn ? S.conv.src.title(panelIndex + 1) : S.conv.docsTitle(panelIndex + 1)) : S.conv.docsTitleNone;

  return (
    <div className={styles.page}>
      <BackLink to={backTo} />

      <Card as="header" className={styles.header}>
        <div className={styles.headerMain}>
          {/* Tiêu đề = câu hỏi cuối, khớp cột "Hội thoại" ở danh sách (last_query; Toma chốt 2026-11-18, WU-10). */}
          <h1 className={styles.title}>{last?.query_origin || S.conv.title}</h1>
          <div className={styles.meta}>
            {first && <span>{S.conv.channelLabel} <strong>{channelLabel(first.channel)}</strong></span>}
            {timeRange && <span>{timeRange}</span>}
          </div>
        </div>
        <div className={styles.counts}>
          {counts.map(({ status, count }) => (
            <Badge key={status} tone={statusTone(status)}>{S.conv.statusCount(count, statusLabel(status))}</Badge>
          ))}
        </div>
      </Card>

      <div className={styles.panes}>
        <Card className={styles.panel} aria-labelledby="turns-title">
          <div className={styles.panelHead}>
            <h2 id="turns-title" className={styles.panelTitle}>{S.conv.turnsTitle}</h2>
            <span className={styles.panelMeta}>{S.conv.turnsMeta(turns.length)}</span>
          </div>
          <div className={styles.panelBody} ref={scrollRef}>
            {hidden > 0 ? (
              <Button className={styles.older} onClick={loadOlder}>{S.conv.loadOlder(Math.min(hidden, TURN_PAGE_SIZE))}</Button>
            ) : (
              first && (
                <div className={styles.startMark} role="note">
                  <span aria-hidden="true" />
                  {S.conv.startOf(formatFullDateTime(askedAt(first) || first.created_at))}
                  <span aria-hidden="true" />
                </div>
              )
            )}
            {shown.map((turn) => (
              <Turn
                key={turn.id}
                turn={turn}
                no={turns.indexOf(turn) + 1}
                sessionId={sessionId}
                from={from}
                phone={phone}
                perTurn={perTurn}
                focused={turn.id === focusId}
                query={query}
                selected={turn.id === panelTurnId}
                legacyCount={turn.id === panelTurnId ? legacyCount : 0}
                techOpen={Boolean(tech[turn.id])}
                onToggleTech={() => setTech((prev) => ({ ...prev, [turn.id]: !prev[turn.id] }))}
                onPick={() => pick(turn.id)}
                onOpenSheet={() => setSheetOpen(true)}
              />
            ))}
          </div>
        </Card>

        {!phone && (
          <Card className={styles.panel} aria-labelledby="docs-title">
            <div className={styles.panelHead}>
              <h2 id="docs-title" className={styles.panelTitle}>{panelTitle}</h2>
              {panelTurn && <span className={styles.panelMeta}>“{panelTurn.query_origin}”</span>}
            </div>
            <div className={styles.panelBody} ref={docsRef}>
              {panelBody}
              {!perTurn && <p className={styles.note}>{S.conv.docsOnlyLatest}</p>}
            </div>
          </Card>
        )}
      </div>

      {phone && (
        <Modal open={sheetOpen} onClose={() => setSheetOpen(false)} title={panelTitle} description={panelTurn ? `“${panelTurn.query_origin}”` : undefined}>
          {panelBody}
        </Modal>
      )}
    </div>
  );
}

function Turn({ turn, no, sessionId, from, phone, perTurn, focused, query, selected, legacyCount, techOpen, onToggleTech, onPick, onOpenSheet }) {
  const asked = askedAt(turn);
  const kind = perTurn ? sourceKind(turn.sources, turn.status) : null;
  const picked = selected && !phone && (perTurn || legacyCount > 0);
  const className = [styles.turn, picked && styles.turnPicked, focused && styles.turnFocus].filter(Boolean).join(' ');
  return (
    <article aria-label={`Lượt ${no}`} className={className} data-focus={focused || undefined}>
      <div className={styles.ask}>
        <span className={styles.who}>{S.conv.customerAsked(asked ? formatTime(asked) : '')}</span>
        <div className={styles.askBubble}><Highlight text={turn.query_origin} query={query} /></div>
      </div>
      <div className={styles.answer}>
        <span className={styles.who}>{turn.answer ? S.conv.botAnswered(formatTime(turn.created_at)) : S.conv.botNoAnswer}</span>
        {turn.answer && <div className={styles.answerBubble}>{turn.answer}</div>}
      </div>
      <div className={styles.statusRow}>
        <Badge tone={statusTone(turn.status)}>{statusLabel(turn.status)}</Badge>
        {statusNote(turn.status) && <span className={styles.statusNote}>{statusNote(turn.status)}</span>}
      </div>
      <div className={styles.actions}>
        {perTurn && kind && (
          <button
            type="button"
            className={`${styles.link} ${styles.srcLabel} ${styles[`srcLabel_${sourceTone(kind)}`] || ''}`}
            aria-pressed={phone ? undefined : selected}
            onClick={onPick}
          >
            {sourceLabel(kind, turn.sources)}
            {selected && !phone ? S.conv.src.viewing : ''}
          </button>
        )}
        {!perTurn && legacyCount > 0 && (
          phone ? (
            <button type="button" className={styles.link} onClick={onOpenSheet}>{S.conv.docsUsed(legacyCount)}</button>
          ) : (
            <span className={styles.docsTag}>{`${S.conv.docsUsed(legacyCount)} · ${S.conv.docsViewing}`}</span>
          )
        )}
        <button type="button" className={`${styles.link} ${styles.muted}`} aria-expanded={techOpen} onClick={onToggleTech}>
          {techOpen ? S.conv.techHide : S.conv.techShow}
        </button>
      </div>
      {techOpen && (
        <div className={styles.tech}>
          <span>{S.conv.techLatency}<b>{formatDuration(turn.latency_ms)}</b></span>
          {turn.usage?.source === 'trace' ? (
            <>
              <span>{S.conv.techTokensReal}<b>{`${formatNumber(turn.input_tokens)} / ${formatNumber(turn.output_tokens)}`}</b></span>
              <span>{S.conv.techLlmCalls}<b>{formatNumber(turn.usage.llm_calls)}</b></span>
              <span>
                {S.conv.techCostReal}
                <b>{turn.cost_vnd != null ? formatVnd(turn.cost_vnd) : formatUsd(turn.cost_usd)}</b>
                {turn.usage.unpriced_models?.length > 0 && <small>{S.conv.techUnpriced(turn.usage.unpriced_models)}</small>}
              </span>
            </>
          ) : (
            <>
              <span>{S.conv.techTokens}<b>{formatNumber(turn.total_tokens)}</b></span>
              <span>{S.conv.techCost}<b>{turn.cost_vnd != null ? formatVnd(turn.cost_vnd) : formatUsd(turn.cost_usd)}</b></span>
            </>
          )}
          <span>{S.conv.techModel}<b>{turn.model || '—'}</b></span>
          <span>
            {S.conv.techTrace}
            <Link to={traceLink(sessionId, turn.id)} state={{ from }}>{S.conv.viewTrace}</Link>
          </span>
          {turn.usage?.source === 'estimate' && <p className={styles.techNote}>{S.conv.techEstimateNote}</p>}
        </div>
      )}
    </article>
  );
}
