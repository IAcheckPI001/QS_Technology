// Lịch sử hội thoại (mock màn 1, điện thoại M2; Q12–Q16, Q19, Q26, Q29).
// B2: máy chủ lọc trên toàn bộ dữ liệu, chia trang 25 hội thoại; 4 ô số liệu và "x / y" tính theo
// cùng bộ lọc (GET /chatbot/conversations/metrics; máy chủ chưa bật route thì ẩn các ô số liệu).
// Tìm không dấu trong câu hỏi của mọi lượt; dòng khớp ở lượt khác lượt cuối ghi "Khớp ở lượt N" và
// mở chi tiết đúng lượt đó.

import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { MessagesSquare, SearchX } from 'lucide-react';
import { CONVERSATION_PAGE_SIZE, conversationsApi } from '../../api/conversations.js';
import Highlight from '../../components/Highlight.jsx';
import { Badge, Button, Card, EmptyState, ErrorBanner, LoadMore, PageHeader, Skeleton } from '../../components/ui.jsx';
import { useCursorList } from '../../hooks/useCursorList.js';
import { PHONE_QUERY, useMediaQuery } from '../../hooks/useMediaQuery.js';
import { useResource } from '../../hooks/useResource.js';
import { useUrlFilters } from '../../hooks/useUrlFilters.js';
import { S } from '../../strings.vi.js';
import { formatDayTime, formatNumber, formatVnd } from '../../utils/format.js';
import { DesktopFilters, MobileFilters, RangeChip } from './ConversationFilters.jsx';
import { FILTER_DEFAULTS, toApiFilters } from './filterModel.js';
import { channelLabel, statusLabel, statusTone } from './status.js';
import { DEFAULT_TIME, activeRange, formatIsoDate, vnToday } from './timeRange.js';
import styles from './conversations.module.css';

const DEFAULTS = FILTER_DEFAULTS;
const SEARCH_DELAY = 300;

export default function ConversationsPage() {
  const [filters, setFilters, resetFilters] = useUrlFilters(DEFAULTS);
  const [query, setQuery] = useState(filters.q);
  const location = useLocation();

  // Gõ xong 300 ms mới ghi lên URL (và tải lại); URL đổi từ ngoài (Xoá bộ lọc, quay lại) thì cập nhật ô.
  useEffect(() => {
    if (query === filters.q) return undefined;
    const timer = setTimeout(() => setFilters({ q: query.trim() === '' ? '' : query }), SEARCH_DELAY);
    return () => clearTimeout(timer);
  }, [query, filters.q, setFilters]);
  const [lastUrlQ, setLastUrlQ] = useState(filters.q);
  if (lastUrlQ !== filters.q) {
    setLastUrlQ(filters.q);
    setQuery(filters.q);
  }

  const phone = useMediaQuery(PHONE_QUERY);
  const [rangeOpen, setRangeOpen] = useState(false);
  const today = vnToday();
  const range = activeRange(filters, today);
  const key = JSON.stringify(toApiFilters(filters, today));
  const apiFilters = useMemo(() => JSON.parse(key), [key]);
  const status = apiFilters.status;

  const fetchPage = useCallback(({ cursor, signal }) => conversationsApi.listPage(apiFilters, { cursor, signal }), [apiFilters]);
  const list = useCursorList(fetchPage, key);
  const metrics = useResource(({ signal }) => conversationsApi.metrics(apiFilters, { signal }), [key]);

  const period = range.custom
    ? S.conv.time.periodCustom(formatIsoDate(range.from), formatIsoDate(range.to))
    : S.conv.time.period[range.preset];
  const filtered = Boolean(apiFilters.q || status || filters.channel || filters.model || filters.time !== DEFAULT_TIME);
  const clearAll = () => {
    setQuery('');
    resetFilters();
  };

  return (
    <div className={styles.page}>
      <PageHeader title={S.conv.title} description={S.conv.description} />

      {phone ? (
        <MobileFilters filters={filters} setFilters={setFilters} query={query} setQuery={setQuery} range={range} today={today} />
      ) : (
        <>
          <DesktopFilters
            filters={filters}
            setFilters={setFilters}
            query={query}
            setQuery={setQuery}
            range={range}
            today={today}
            rangeOpen={rangeOpen}
            setRangeOpen={setRangeOpen}
          />
          {range.custom && (
            <RangeChip range={range} onEdit={() => setRangeOpen(true)} onClear={() => setFilters({ time: DEFAULT_TIME, from: '', to: '' })} />
          )}
        </>
      )}

      {metrics.data !== null && (
        <Metrics data={metrics.data} loading={metrics.loading} error={metrics.error} onRetry={metrics.reload} period={period} />
      )}

      <Card aria-label={S.conv.title} className={styles.listCard}>
        {list.loading ? (
          <ListSkeleton />
        ) : list.error && list.items.length === 0 ? (
          <div className={styles.pad}><ErrorBanner error={list.error} onRetry={list.reload} /></div>
        ) : list.items.length === 0 ? (
          filtered ? (
            <EmptyState icon={SearchX} title={S.conv.emptyTitle} body={S.conv.emptyBody} action={<Button onClick={clearAll}>{S.conv.clearFilters}</Button>} />
          ) : (
            <EmptyState icon={MessagesSquare} title={S.conv.emptyAllTitle} body={S.conv.emptyAllBody} />
          )
        ) : (
          <>
            <ConversationTable items={list.items} from={location.search} query={apiFilters.q} />
            <ConversationCards items={list.items} from={location.search} query={apiFilters.q} />
            <LoadMore
              count={list.items.length}
              total={metrics.data?.conversation_count ?? null}
              noun={S.conv.noun}
              pageSize={CONVERSATION_PAGE_SIZE}
              loading={list.loadingMore}
              done={list.done}
              error={list.error}
              onLoadMore={list.loadMore}
            />
          </>
        )}
      </Card>
    </div>
  );
}

// ---- Ô số liệu (Q12: không có token) -------------------------------------------------------------

function Metrics({ data, loading, error, onRetry, period }) {
  if (error) return <ErrorBanner error={error} onRetry={onRetry} />;
  const value = (number) => (loading || !data ? '…' : number);
  const tiles = [
    { label: S.conv.metric.conversations, value: value(formatNumber(data?.conversation_count)), hint: period },
    { label: S.conv.metric.handoffs, value: value(formatNumber(data?.handoff_count)), hint: S.conv.metric.handoffsHint(period) },
    { label: S.conv.metric.questions, value: value(formatNumber(data?.question_count)), hint: S.conv.metric.questionsHint(period) },
    { label: S.conv.metric.cost, value: value(formatVnd(data?.cost_vnd)), hint: S.conv.metric.costHint(period), estimate: true },
  ];
  return (
    <section className={styles.metrics} aria-label={S.conv.metrics} aria-busy={loading || undefined}>
      {tiles.map((tile) => (
        <Card key={tile.label} className={styles.metric}>
          <div className={styles.metricHead}>
            <span className={styles.metricLabel}>{tile.label}</span>
            {tile.estimate && <Badge tone="warning">{S.conv.estimate}</Badge>}
          </div>
          <strong className={styles.metricValue}>{tile.value}</strong>
          <span className={styles.metricHint}>{tile.hint}</span>
        </Card>
      ))}
    </section>
  );
}

// ---- Danh sách ------------------------------------------------------------------------------------

/** Link chi tiết; khớp tìm kiếm thì thêm `turn` (lượt khớp) và `q` (để tô từ khoá) vào URL. */
function detailLink(item, query) {
  const turn = item.match?.history_id;
  const params = new URLSearchParams();
  if (turn) {
    params.set('turn', turn);
    if (query) params.set('q', query);
  }
  const search = params.toString();
  return { pathname: `/conversations/${encodeURIComponent(item.session_id)}`, search: search ? `?${search}` : '' };
}

function Tags({ item }) {
  const models = item.product_models || [];
  if (!models.length && !item.ticket_id) return null;
  return (
    <span className={styles.tags}>
      {models.map((model) => <Badge key={model}>{model}</Badge>)}
      {item.ticket_id && <Badge tone="brand">#{item.ticket_id}</Badge>}
    </span>
  );
}

/** Tiêu đề dòng (câu hỏi cuối) và, nếu lượt khớp là lượt khác, dòng "Khớp ở lượt N: …" có tô sáng. */
function Title({ item, from, query }) {
  const match = item.match;
  const otherTurn = match && match.query !== item.last_query;
  return (
    <>
      {/* state.from: bộ lọc của danh sách, để nút quay lại giữ nguyên bộ lọc. */}
      <Link className={styles.rowLink} to={detailLink(item, query)} state={{ from }}>
        <Highlight text={item.last_query} query={query} />
      </Link>
      {otherTurn && (
        <span className={styles.matchLine}>
          {S.conv.matchAt(match.turn_number)}
          <Highlight text={match.query} query={query} />
        </span>
      )}
    </>
  );
}

const cost = (item) => (item.cost_vnd != null ? formatVnd(item.cost_vnd) : '—');

function ConversationTable({ items, from, query }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">{S.conv.colConversation}</th>
            <th scope="col">{S.conv.colChannel}</th>
            <th scope="col">{S.conv.colStarted}</th>
            <th scope="col">{S.conv.colLast}</th>
            <th scope="col" className={styles.num}>{S.conv.colQuestions}</th>
            <th scope="col">{S.conv.colStatus}</th>
            <th scope="col" className={styles.num}>{S.conv.colCost}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.session_id}>
              <td className={styles.titleCell}>
                <Title item={item} from={from} query={query} />
                <Tags item={item} />
              </td>
              <td>{channelLabel(item.channel)}</td>
              <td className={styles.time}>{formatDayTime(item.created_at)}</td>
              <td className={styles.time}>{formatDayTime(item.updated_date)}</td>
              <td className={styles.num}>{item.question_count != null ? formatNumber(item.question_count) : '—'}</td>
              <td><Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge></td>
              <td className={`${styles.num} ${styles.time}`}>{cost(item)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConversationCards({ items, from, query }) {
  return (
    <ul className={styles.cards}>
      {items.map((item) => (
        <li key={item.session_id} className={styles.cardItem}>
          <Title item={item} from={from} query={query} />
          <span className={styles.cardMeta}>
            <Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge>
            <span>{channelLabel(item.channel)}</span>
            <span>·</span>
            <span>{formatDayTime(item.updated_date)}</span>
            {item.question_count != null && (
              <>
                <span>·</span>
                <span>{S.conv.questions(item.question_count)}</span>
              </>
            )}
          </span>
          <Tags item={item} />
        </li>
      ))}
    </ul>
  );
}

function ListSkeleton() {
  return (
    <div className={styles.skeleton} role="status" aria-label={S.common.loading}>
      {Array.from({ length: 6 }, (_, i) => (
        <div key={i} className={styles.skeletonRow}>
          <Skeleton width="45%" height={14} />
          <Skeleton width="12%" height={14} />
          <Skeleton width="14%" height={14} />
          <Skeleton width="10%" height={20} />
        </div>
      ))}
    </div>
  );
}
