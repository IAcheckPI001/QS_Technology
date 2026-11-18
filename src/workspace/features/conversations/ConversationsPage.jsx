// Lịch sử hội thoại (mock màn 1, điện thoại M2; Q12–Q16, Q19, Q26).
// Trước B2 (FRONTEND_REQUIREMENTS 19.13): chỉ ô tìm (lượt mới nhất) và lọc trạng thái; ẩn Kênh, Thời
// gian, Model sản phẩm, các ô số liệu, cột Số câu hỏi và Chi phí AI. "Tải thêm" cắt trang trên danh
// sách đầy đủ do API hiện trả hết một lần.

import { useCallback, useEffect, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { MessagesSquare, SearchX } from 'lucide-react';
import { CONVERSATION_PAGE_SIZE, conversationsApi } from '../../api/conversations.js';
import { Badge, Button, Card, EmptyState, ErrorBanner, LoadMore, PageHeader, SelectField, Skeleton, TextField } from '../../components/ui.jsx';
import { useCursorList } from '../../hooks/useCursorList.js';
import { useUrlFilters } from '../../hooks/useUrlFilters.js';
import { S } from '../../strings.vi.js';
import { formatDayTime } from '../../utils/format.js';
import { STATUS_FILTER_OPTIONS, channelLabel, statusLabel, statusTone } from './status.js';
import styles from './conversations.module.css';

const DEFAULTS = { q: '', status: '' };
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

  const search = filters.q.trim();
  const status = filters.status;
  const fetchPage = useCallback(
    ({ cursor, signal }) => conversationsApi.listPage({ search, status }, { cursor, signal }),
    [search, status],
  );
  const list = useCursorList(fetchPage, JSON.stringify([search, status]));
  const filtered = Boolean(search || status);
  const clearAll = () => {
    setQuery('');
    resetFilters();
  };

  return (
    <div className={styles.page}>
      <PageHeader title={S.conv.title} description={S.conv.description} />

      <Card className={styles.filters} aria-label={S.conv.filters}>
        <TextField
          className={styles.searchField}
          type="search"
          label={S.conv.search}
          placeholder={S.conv.searchPlaceholder}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <SelectField
          className={styles.statusField}
          label={S.conv.statusLabel}
          value={status}
          options={STATUS_FILTER_OPTIONS}
          onChange={(event) => setFilters({ status: event.target.value })}
        />
        <p className={styles.pending}>{S.conv.pendingBackend}</p>
      </Card>

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
            <ConversationTable items={list.items} from={location.search} />
            <ConversationCards items={list.items} from={location.search} />
            <LoadMore
              count={list.items.length}
              total={list.total}
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

function detailLink(item, from) {
  return { pathname: `/conversations/${encodeURIComponent(item.session_id)}`, state: { from } };
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

function ConversationTable({ items, from }) {
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th scope="col">{S.conv.colConversation}</th>
            <th scope="col">{S.conv.colChannel}</th>
            <th scope="col">{S.conv.colStarted}</th>
            <th scope="col">{S.conv.colLast}</th>
            <th scope="col">{S.conv.colStatus}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.session_id}>
              <td className={styles.titleCell}>
                <Link className={styles.rowLink} to={detailLink(item, from)}>{item.last_query}</Link>
                <Tags item={item} />
              </td>
              <td>{channelLabel(item.channel)}</td>
              <td className={styles.time}>{formatDayTime(item.created_at)}</td>
              <td className={styles.time}>{formatDayTime(item.updated_date)}</td>
              <td><Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ConversationCards({ items, from }) {
  return (
    <ul className={styles.cards}>
      {items.map((item) => (
        <li key={item.session_id} className={styles.cardItem}>
          <Link className={styles.rowLink} to={detailLink(item, from)}>{item.last_query}</Link>
          <span className={styles.cardMeta}>
            <Badge tone={statusTone(item.status)}>{statusLabel(item.status)}</Badge>
            <span>{channelLabel(item.channel)}</span>
            <span>·</span>
            <span>{formatDayTime(item.updated_date)}</span>
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
