// Mã trích dẫn `[S1]` trong câu trả lời (prompts/answer.py) → link nội bộ `#cite-S1` để
// Markdown.jsx render thành huy hiệu. Phần code (```…``` và `…`) giữ nguyên.

export const CITE_HREF = '#cite-';

const CITE_RE = /\[(S\d+)\]/g;
const CODE_RE = /(```[\s\S]*?(?:```|$)|`[^`\n]*`)/g;

export function linkCitations(text) {
  return String(text || '')
    .split(CODE_RE)
    .map((part, index) => (index % 2 === 1 ? part : part.replace(CITE_RE, `[$1](${CITE_HREF}$1)`)))
    .join('');
}

/** "S12" → "12". */
export const citationNumber = (id) => String(id).replace(/^S/, '');
