// Render câu trả lời của chatbot (Markdown + bảng GFM) cho widget và Workspace.
// - Không render HTML thô trong câu trả lời; ảnh trong markdown chỉ hiện chữ thay thế.
// - Link chỉ nhận http(s)/mailto, mở tab mới; link khác hiện như chữ.
// - Mã trích dẫn `[S1]` thành huy hiệu tròn qua `renderCitation(id)`; không truyền thì dùng
//   huy hiệu mặc định (chỉ hiện số). Không đổi trong khối code.

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CITE_HREF, citationNumber, linkCitations } from './markdownCitations.js';
import styles from './Markdown.module.css';

const SAFE_LINK = /^(https?:|mailto:)/i;

function DefaultCitation({ id }) {
  return (
    <span className={styles.cite} aria-label={`Nguồn ${id}`}>
      {citationNumber(id)}
    </span>
  );
}

export default function Markdown({ text, className, renderCitation }) {
  const components = {
    a({ href = '', children }) {
      if (href.startsWith(CITE_HREF)) {
        const id = href.slice(CITE_HREF.length);
        return renderCitation ? renderCitation(id) : <DefaultCitation id={id} />;
      }
      if (!SAFE_LINK.test(href)) return <span>{children}</span>;
      return (
        <a href={href} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      );
    },
    img({ alt }) {
      return alt ? <span>{`[${alt}]`}</span> : null;
    },
    table({ children }) {
      return (
        <div className={styles.tableWrap}>
          <table>{children}</table>
        </div>
      );
    },
  };
  return (
    <div className={[styles.md, className].filter(Boolean).join(' ')}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} skipHtml components={components}>
        {linkCitations(text)}
      </ReactMarkdown>
    </div>
  );
}
