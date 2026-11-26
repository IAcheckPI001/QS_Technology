// Ngăn "Thư mục tài liệu": nhóm (nhánh CRM) › thư mục sản phẩm › tài liệu, chấm màu theo trạng thái.
// Nhóm chatbot đang dùng mở sẵn; nhóm khác thu gọn, chữ xám.

import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, ChevronRight, Folder } from 'lucide-react';
import { ErrorBanner, SkeletonBlock } from '../../components/ui.jsx';
import { formatFullDateTime } from '../../utils/format.js';
import { S } from '../../strings.vi.js';
import { STATUS_DOT } from './documentModel.js';
import styles from './documents.module.css';

function Toggle({ open, onClick, label, count, muted, children, strong }) {
  return (
    <button type="button" className={`${styles.trow} ${muted ? styles.muted : ''} ${strong ? styles.strong : ''}`} onClick={onClick} aria-expanded={open}>
      {open ? <ChevronDown size={14} aria-hidden="true" /> : <ChevronRight size={14} aria-hidden="true" />}
      {children}
      <span className={styles.tlabel}>{label}</span>
      <span className={styles.tcount}>{count}</span>
    </button>
  );
}

export default function FolderTree({ id, resource, currentDocId, onPick }) {
  const [open, setOpen] = useState({});
  const data = resource.data;
  const isOpen = (key, fallback) => (open[key] === undefined ? fallback : open[key]);
  const toggle = (key, fallback) => setOpen((prev) => ({ ...prev, [key]: !isOpen(key, fallback) }));

  return (
    <nav id={id} className={styles.drawer} aria-label={S.docs.foldersTitle}>
      <div className={styles.drawerHead}>
        <strong>{S.docs.foldersTitle}</strong>
        {data && <span>{S.docs.total(data.document_count)}</span>}
      </div>
      <div className={styles.drawerBody}>
        {resource.loading && !data && <SkeletonBlock lines={6} />}
        {resource.error && <ErrorBanner error={resource.error} onRetry={resource.reload} />}
        {data && (
          <ul className={styles.tree}>
            {data.branches.map((branch) => {
              const branchOpen = isOpen(branch.name, branch.used_by_chatbot);
              return (
                <li key={branch.name}>
                  <Toggle open={branchOpen} onClick={() => toggle(branch.name, branch.used_by_chatbot)} label={branch.name}
                    count={branch.document_count} muted={!branch.used_by_chatbot} strong>
                    <Folder size={16} aria-hidden="true" className={branch.used_by_chatbot ? styles.folderIcon : styles.folderIconMuted} />
                  </Toggle>
                  {branchOpen && (
                    <ul className={styles.tree} style={{ paddingLeft: 14 }}>
                      {!branch.used_by_chatbot && <li className={styles.tnote}>{S.docs.notUsed}</li>}
                      {branch.folders.map((folder) => {
                        const key = `${branch.name}/${folder.name}`;
                        const hasCurrent = folder.documents.some((d) => d.doc_id && d.doc_id === currentDocId);
                        const folderOpen = isOpen(key, hasCurrent || (branch.used_by_chatbot && branch.folders.length <= 8));
                        return (
                          <li key={key}>
                            <Toggle open={folderOpen} onClick={() => toggle(key, hasCurrent)} label={folder.name} count={folder.documents.length}>
                              <Folder size={15} aria-hidden="true" className={styles.folderIcon} />
                            </Toggle>
                            {folderOpen && (
                              <ul className={styles.tree} style={{ paddingLeft: 20 }}>
                                {folder.documents.map((doc) => {
                                  const current = doc.doc_id && doc.doc_id === currentDocId;
                                  const dot = <i className={styles.dot} style={{ background: STATUS_DOT[doc.status] }} aria-hidden="true" />;
                                  const title = `${S.docs.status[doc.status]}${doc.chunk_count ? ` · ${S.docs.approved(doc.approved_count, doc.chunk_count)}` : ''}`;
                                  return (
                                    <li key={doc.crm_id}>
                                      {doc.doc_id ? (
                                        <Link to={`/documents/${encodeURIComponent(doc.doc_id)}`} className={current ? `${styles.tdoc} ${styles.tdocOn}` : styles.tdoc}
                                          aria-current={current ? 'page' : undefined} title={title} onClick={onPick}>
                                          {dot}<span className={styles.tlabel}>{doc.name}</span>
                                          {doc.pending_count > 0 && <span className={styles.pendingDot}>{doc.pending_count > 99 ? '99+' : doc.pending_count}</span>}
                                        </Link>
                                      ) : (
                                        <span className={`${styles.tdoc} ${styles.muted}`} title={title}>{dot}<span className={styles.tlabel}>{doc.name}</span></span>
                                      )}
                                    </li>
                                  );
                                })}
                              </ul>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div className={styles.drawerFoot}>
        <div className={styles.legend}>
          {['live', 'review', 'work', 'idle'].map((s) => (
            <span key={s}><i className={styles.dot} style={{ background: STATUS_DOT[s] }} aria-hidden="true" />{S.docs.status[s]}</span>
          ))}
        </div>
        <span>{data?.synced_at ? S.docs.syncedAt(formatFullDateTime(data.synced_at)) : S.docs.notSynced}</span>
      </div>
    </nav>
  );
}
