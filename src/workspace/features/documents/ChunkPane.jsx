// Khung "Đoạn kiến thức" (mock 5b/5 v4): tìm trong tài liệu, Mục lục (lọc theo mục), tab Tất cả / Chờ duyệt (số đoạn
// trong bong bóng) / Đã duyệt / Có hình, thẻ đoạn, tải thêm. Chỉ đọc: duyệt/sửa chờ đợt sau.

import { useEffect, useRef, useState } from 'react';
import { ListTree, Search, X } from 'lucide-react';
import Markdown from '../../../components/Markdown.jsx';
import { CHUNK_PAGE_SIZE, documentsApi } from '../../api/documents.js';
import { Badge, Button, EmptyState, ErrorBanner, SkeletonBlock } from '../../components/ui.jsx';
import { useResource } from '../../hooks/useResource.js';
import { S } from '../../strings.vi.js';
import { chunkBody, chunkPages, chunkParent, chunkTitle, figureCaptions } from './documentModel.js';
import ImageViewer from './ImageViewer.jsx';
import styles from './documents.module.css';

const LONG = 320;
const TABS = ['all', 'pending', 'approved', 'images'];

function useDebounced(value, ms) {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(timer);
  }, [value, ms]);
  return debounced;
}

function OutlineList({ nodes, active, onPick, depth = 0 }) {
  return (
    <ul className={styles.outlineList}>
      {nodes.map((node) => {
        const key = node.path.join(' › ');
        const on = active.join(' › ') === key;
        return (
          <li key={key}>
            <button type="button" className={on ? `${styles.outlineRow} ${styles.outlineOn}` : styles.outlineRow}
              style={{ paddingLeft: 10 + depth * 14 }} onClick={() => onPick(node.path, node.title)} aria-current={on ? 'true' : undefined}>
              <span className={styles.tlabel}>{node.title}</span><span className={styles.tcount}>{node.chunk_count}</span>
            </button>
            {node.children.length > 0 && depth < 3 && <OutlineList nodes={node.children} active={active} onPick={onPick} depth={depth + 1} />}
          </li>
        );
      })}
    </ul>
  );
}

function ChunkCard({ chunk, selected, onSelect, onOpenPage }) {
  const [open, setOpen] = useState(false);
  const [zoom, setZoom] = useState(null);   // chỉ số hình đang xem to
  const body = chunkBody(chunk);
  const long = body.length > LONG;
  const parent = chunkParent(chunk);
  return (
    <article
      id={`chunk-${chunk.id}`}
      className={selected ? `${styles.chunk} ${styles.chunkOn}` : styles.chunk}
      aria-label={chunkTitle(chunk)}
      onClick={() => onSelect(chunk)}
    >
      <div className={styles.chunkHead}>
        <div className={styles.chunkTitles}>
          <strong>{chunkTitle(chunk)}</strong>
          {parent && <span className={styles.chunkParent}>{parent}</span>}
        </div>
        <Badge tone={chunk.review_status === 'approved' ? 'success' : 'warning'}>{S.docs.chunkStatus[chunk.review_status]}</Badge>
      </div>
      <div className={styles.chunkMeta}>
        <span>{S.docs.chunkType[chunk.chunk_type] || S.docs.chunkTypeOther}</span>
        {chunkPages(chunk) && <span>{chunkPages(chunk)}</span>}
        {chunk.printed_page_start != null && <span>{S.docs.printed(chunk.printed_page_start)}</span>}
        {chunk.image_count > 0 && <span>{S.docs.images(chunk.image_count)}</span>}
      </div>
      {body && <Markdown text={body} className={long && !open ? `${styles.chunkBody} ${styles.clamp}` : styles.chunkBody} />}
      {long && (
        <button type="button" className={styles.link} aria-expanded={open} onClick={(event) => { event.stopPropagation(); setOpen(!open); }}>
          {open ? S.docs.showLess : S.docs.showMore(body.length)}
        </button>
      )}
      {chunk.images.length > 0 && (
        <div className={styles.chunkImages}>
          {chunk.images.map((image, i) => (
            <button key={image.url} type="button" className={styles.thumb} aria-label={S.docs.viewer.zoom(figureCaptions(chunk.content)[i] || S.docs.viewer.figure(i + 1, chunk.images.length))}
              onClick={(event) => { event.stopPropagation(); setZoom(i); }}>
              <img src={image.url} alt="" loading="lazy" referrerPolicy="no-referrer" />
            </button>
          ))}
        </div>
      )}
      {zoom != null && (
        <div onClick={(event) => event.stopPropagation()}>
          <ImageViewer images={chunk.images} index={zoom} title={chunkTitle(chunk)} captions={figureCaptions(chunk.content)}
            onIndex={setZoom} onClose={() => setZoom(null)} onOpenPage={(page) => { setZoom(null); onOpenPage(page); }} />
        </div>
      )}
      <div className={styles.ai}>
        <span className={styles.aiLabel}>{S.docs.summary}</span>
        <span>{chunk.summary_vi || S.docs.noSummary}</span>
        {chunk.keywords.length > 0 && (
          <div className={styles.keywords} aria-label={S.docs.keywords}>
            {chunk.keywords.slice(0, 10).map((word) => <span key={word}>{word}</span>)}
          </div>
        )}
      </div>
    </article>
  );
}

export default function ChunkPane({ docId, doc, onPickPage, className = '' }) {
  const [tab, setTab] = useState('all');
  const [text, setText] = useState('');
  const q = useDebounced(text, 300);
  const [section, setSection] = useState({ path: [], title: '' });
  const [outlineOpen, setOutlineOpen] = useState(false);
  const [selected, setSelected] = useState(null);
  const [pages, setPages] = useState({ items: [], total: 0, loadingMore: false, error: null });
  const listRef = useRef(null);
  const filters = { tab, q, section: section.path };

  const first = useResource(
    ({ signal }) => documentsApi.chunks(docId, filters, { offset: 0, signal }),
    [docId, tab, q, section.path.join('\u0000')],
  );
  const outline = useResource(
    ({ signal }) => (outlineOpen ? documentsApi.outline(docId, { signal }) : Promise.resolve(null)),
    [docId, outlineOpen],
  );

  useEffect(() => {
    if (first.data) setPages({ items: first.data.items, total: first.data.total, loadingMore: false, error: null });
    if (listRef.current) listRef.current.scrollTop = 0;
  }, [first.data]);

  const loadMore = async () => {
    setPages((p) => ({ ...p, loadingMore: true, error: null }));
    try {
      const data = await documentsApi.chunks(docId, filters, { offset: pages.items.length });
      setPages((p) => ({ items: [...p.items, ...data.items], total: data.total, loadingMore: false, error: null }));
    } catch (error) {
      setPages((p) => ({ ...p, loadingMore: false, error }));
    }
  };

  const pick = (chunk) => {
    setSelected(chunk.id);
    if (chunk.page_start != null) onPickPage(chunk.page_start);
  };

  const pending = doc ? doc.pending_count : null;
  const done = pages.items.length >= pages.total;

  return (
    <section className={`${styles.chunkPane} ${className}`} aria-label={S.docs.chunksTitle}>
      <div className={styles.chunkTools}>
        <div className={styles.searchRow}>
          <Button icon={ListTree} onClick={() => setOutlineOpen((open) => !open)} aria-expanded={outlineOpen} aria-controls="doc-outline">
            {S.docs.outline}
          </Button>
          <label className={styles.search}>
            <Search size={16} aria-hidden="true" />
            <span className="ws-visually-hidden">{S.docs.search}</span>
            <input type="search" value={text} placeholder={S.docs.searchPlaceholder} onChange={(event) => setText(event.target.value)} />
          </label>
        </div>
        <div className={styles.tabs} role="tablist" aria-label={S.docs.chunksTitle}>
          {TABS.map((id) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id} className={tab === id ? `${styles.tab} ${styles.tabOn}` : styles.tab}
              onClick={() => setTab(id)} aria-label={id === 'pending' && pending != null ? S.docs.pendingAria(pending) : undefined}>
              {S.docs.tabs[id]}
              {id === 'pending' && pending > 0 && <span className={styles.countDot} aria-hidden="true">{pending > 99 ? '99+' : pending}</span>}
            </button>
          ))}
          <span className={styles.chunkCount}>{first.data ? S.docs.chunkCount(pages.items.length, pages.total) : ''}</span>
        </div>
        {section.path.length > 0 && (
          <div className={styles.sectionChip}>
            <span>{S.docs.sectionFilter(section.title)}</span>
            <button type="button" onClick={() => setSection({ path: [], title: '' })} aria-label={S.docs.clearSection}><X size={14} aria-hidden="true" /></button>
          </div>
        )}
        <p className={styles.readOnly}>{S.docs.readOnly}</p>
      </div>

      <div className={styles.chunkScroll} ref={listRef}>
        {outlineOpen && (
          <div id="doc-outline" className={styles.outline} role="dialog" aria-label={S.docs.outline}>
            <div className={styles.outlineHead}>
              <strong>{S.docs.outline}</strong>
              <button type="button" className={styles.iconBtn} onClick={() => setOutlineOpen(false)} aria-label={S.docs.outlineClose}><X size={16} aria-hidden="true" /></button>
            </div>
            {outline.loading && <SkeletonBlock lines={6} />}
            {outline.error && <ErrorBanner error={outline.error} onRetry={outline.reload} />}
            {outline.data && (
              <>
                <button type="button" className={styles.outlineRow} onClick={() => { setSection({ path: [], title: '' }); setOutlineOpen(false); }}>
                  <span className={styles.tlabel}>{S.docs.outlineAll}</span><span className={styles.tcount}>{outline.data.total}</span>
                </button>
                <OutlineList nodes={outline.data.nodes} active={section.path} onPick={(path, title) => { setSection({ path, title }); setOutlineOpen(false); }} />
              </>
            )}
          </div>
        )}
        {first.loading && !first.data && <SkeletonBlock lines={6} />}
        {first.error && <ErrorBanner error={first.error} onRetry={first.reload} />}
        {first.data && pages.items.length === 0 && (
          <EmptyState icon={Search}
            title={!q && !section.path.length && S.docs.emptyTab[tab] ? S.docs.emptyTab[tab][0] : S.docs.noChunksTitle}
            body={!q && !section.path.length && S.docs.emptyTab[tab] ? S.docs.emptyTab[tab][1] : S.docs.noChunksBody} />
        )}
        {pages.items.map((chunk) => (
          <ChunkCard key={chunk.id} chunk={chunk} selected={chunk.id === selected} onSelect={pick}
            onOpenPage={(page) => { setSelected(chunk.id); onPickPage(page); }} />
        ))}
        {pages.error && <ErrorBanner error={pages.error} onRetry={loadMore} />}
        {first.data && !done && (
          <Button className={styles.more} onClick={loadMore} loading={pages.loadingMore}>
            {S.docs.loadMore(Math.min(CHUNK_PAGE_SIZE, pages.total - pages.items.length))}
          </Button>
        )}
      </div>
    </section>
  );
}
