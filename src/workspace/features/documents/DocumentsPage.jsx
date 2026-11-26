// Tài liệu & chunk (mock "5 v4", canvas v87): một màn gồm thư mục tài liệu (ẩn/hiện bằng nút ở thanh trên), PDF và
// đoạn kiến thức. Phần đọc trên B6 (/workspace/documents); duyệt, sửa đoạn chờ đợt sau (cần B1).
// - /documents: mở tài liệu đầu tiên có đoạn kiến thức.
// - /documents/:docId: tài liệu đó; bấm một đoạn thì PDF nhảy tới trang của đoạn.

import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ChevronRight, ExternalLink, Download, FileSearch, Folder, FolderX } from 'lucide-react';
import { documentsApi } from '../../api/documents.js';
import { Badge, Card, EmptyState, ErrorBanner, SkeletonBlock } from '../../components/ui.jsx';
import { useResource } from '../../hooks/useResource.js';
import { S } from '../../strings.vi.js';
import ChunkPane from './ChunkPane.jsx';
import FolderTree from './FolderTree.jsx';
import { firstReadable, STATUS_TONE } from './documentModel.js';
import styles from './documents.module.css';

export default function DocumentsPage() {
  const { docId } = useParams();
  const navigate = useNavigate();
  const [foldersOpen, setFoldersOpen] = useState(!docId);
  const [page, setPage] = useState(null);
  const [pane, setPane] = useState('chunks');   // điện thoại: chỉ hiện một khung
  const tree = useResource(({ signal }) => documentsApi.tree({ signal }), []);
  const detail = useResource(
    ({ signal }) => (docId ? documentsApi.detail(docId, { signal }) : Promise.resolve(null)),
    [docId],
  );

  // /documents: tự mở tài liệu đầu tiên có đoạn kiến thức.
  const first = tree.data ? firstReadable(tree.data) : null;
  useEffect(() => {
    if (!docId && first) navigate(`/documents/${encodeURIComponent(first)}`, { replace: true });
  }, [docId, first, navigate]);

  useEffect(() => {
    setPage(null);
  }, [docId]);

  if (tree.error?.kind === 'not_found') {
    return (
      <div className={styles.page}>
        <Card><EmptyState icon={FolderX} title={S.docs.offTitle} body={S.docs.offBody} /></Card>
      </div>
    );
  }

  const doc = detail.data;
  const pdfPage = page || 1;

  return (
    <div className={styles.page}>
      <header className={styles.top}>
        <button
          type="button"
          className={foldersOpen ? `${styles.folderBtn} ${styles.folderBtnOn}` : styles.folderBtn}
          onClick={() => setFoldersOpen((open) => !open)}
          aria-expanded={foldersOpen}
          aria-controls="doc-folders"
          title={foldersOpen ? S.docs.foldersHide : S.docs.foldersShow}
        >
          <Folder size={18} aria-hidden="true" />
          {S.docs.folders}
          <ChevronRight size={16} className={styles.arrow} aria-hidden="true" />
        </button>
        <div className={styles.titleBlock}>
          {doc ? (
            <>
              <nav aria-label="Vị trí" className={styles.crumbs}>
                <Link to="/documents">{S.nav.documents}</Link> › {doc.branch}{doc.folder ? ` › ${doc.folder}` : ''}
              </nav>
              <div className={styles.titleRow}>
                <h1 className={styles.title}>{doc.name}</h1>
                {doc.version && <Badge>{S.docs.version(doc.version)}</Badge>}
                <Badge tone={STATUS_TONE[doc.status]}>
                  {doc.status === 'review' || doc.status === 'live' ? `${S.docs.status[doc.status]} · ${S.docs.approved(doc.approved_count, doc.chunk_count)}` : S.docs.status[doc.status]}
                </Badge>
                {!doc.on_crm && <Badge tone="danger">{S.docs.offCrm}</Badge>}
              </div>
              <span className={styles.meta}>{S.docs.meta(S.docs.type[doc.document_type] || doc.document_type, S.docs.lang[doc.language] || doc.language, doc.page_count)}</span>
            </>
          ) : (
            <h1 className={styles.title}>{S.nav.documents}</h1>
          )}
        </div>
        {doc && (
          <div className={styles.actions}>
            <a className={styles.linkBtn} href={documentsApi.pdfUrl(doc.doc_id, 'view')} target="_blank" rel="noopener noreferrer">
              <ExternalLink size={16} aria-hidden="true" />{S.docs.openPdf}
            </a>
            <a className={styles.linkBtn} href={documentsApi.pdfUrl(doc.doc_id, 'download')} rel="noopener noreferrer">
              <Download size={16} aria-hidden="true" />{S.docs.downloadPdf}
            </a>
          </div>
        )}
      </header>

      <div className={styles.body}>
        {foldersOpen && (
          <FolderTree id="doc-folders" resource={tree} currentDocId={docId} onPick={() => setFoldersOpen(false)} />
        )}
        {!docId ? (
          <Card className={styles.placeholder}>
            {tree.loading ? <SkeletonBlock lines={4} /> : tree.error ? <ErrorBanner error={tree.error} onRetry={tree.reload} />
              : <EmptyState icon={FileSearch} title={first === null && tree.data?.document_count === 0 ? S.docs.emptyTitle : S.docs.pickTitle} body={tree.data?.document_count === 0 ? S.docs.emptyBody : S.docs.pickBody} />}
          </Card>
        ) : detail.error ? (
          <Card className={styles.placeholder}><ErrorBanner error={detail.error} onRetry={detail.reload} /></Card>
        ) : (
          <>
            <div className={styles.paneSwitch} role="tablist" aria-label={S.docs.chunksTitle}>
              {['chunks', 'pdf'].map((id) => (
                <button key={id} type="button" role="tab" aria-selected={pane === id}
                  className={pane === id ? `${styles.tab} ${styles.tabOn}` : styles.tab} onClick={() => setPane(id)}>
                  {S.docs.panes[id]}
                </button>
              ))}
            </div>
            <section className={pane === 'pdf' ? styles.pdfPane : `${styles.pdfPane} ${styles.paneOff}`} aria-label={S.docs.pdfTitle}>
              <div className={styles.paneHead}>
                <span>{S.docs.pdfPage(pdfPage)}</span>
              </div>
              {doc ? (
                <iframe
                  key={`${doc.doc_id}:${pdfPage}`}
                  className={styles.pdf}
                  title={`${S.docs.pdfTitle}: ${doc.name}`}
                  src={`${documentsApi.pdfUrl(doc.doc_id, 'view')}#page=${pdfPage}`}
                />
              ) : (
                <SkeletonBlock lines={6} />
              )}
              <p className={styles.pdfHint}>{S.docs.pdfHint}</p>
            </section>
            <ChunkPane key={docId} docId={docId} doc={doc} className={pane === 'chunks' ? '' : styles.paneOff}
              onPickPage={(n) => { setPage(n); setPane('pdf'); }} />
          </>
        )}
      </div>
    </div>
  );
}
