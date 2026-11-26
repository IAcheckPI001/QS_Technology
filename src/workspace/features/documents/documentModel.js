// Hàm thuần của màn Tài liệu & chunk.

import { S } from '../../strings.vi.js';

// Màu trạng thái tài liệu (chấm và badge): live xanh, review vàng, work xanh dương, idle xám.
export const STATUS_TONE = { live: 'success', review: 'warning', work: 'info', idle: 'neutral' };
export const STATUS_DOT = { live: '#1D7A4D', review: '#C27A0E', work: '#2F6C8F', idle: '#A8AFBB' };

/** Tiêu đề hiển thị của đoạn: phần cuối của section_title (sau "›"), bỏ dấu ":" cuối. */
export function chunkTitle(chunk) {
  const parts = String(chunk.section_title || '').split(' › ');
  return parts[parts.length - 1].replace(/:$/, '');
}

/** Mục cha (dòng phụ): đường dẫn mục trừ phần tiêu đề. */
export function chunkParent(chunk) {
  const path = (chunk.section_path || []).filter(Boolean);
  const title = chunkTitle(chunk);
  const parents = path[path.length - 1] === title || path[path.length - 1] === chunk.section_title ? path.slice(0, -1) : path;
  return parents.slice(-2).join(' › ');
}

/** Nội dung bỏ dòng đầu khi trùng tiêu đề (nội dung đoạn hay lặp lại heading). */
export function chunkBody(chunk) {
  const lines = String(chunk.content || '').split('\n');
  return lines[0].replace(/:$/, '').trim() === chunkTitle(chunk) ? lines.slice(1).join('\n').trim() : chunk.content;
}

export function chunkPages(chunk) {
  if (chunk.page_start == null) return '';
  return S.docs.pages(chunk.page_start, chunk.page_end);
}

/** doc_id của tài liệu đầu tiên có đoạn kiến thức (để /documents tự mở). */
export function firstReadable(tree) {
  for (const branch of tree.branches || []) {
    for (const folder of branch.folders || []) {
      const doc = (folder.documents || []).find((d) => d.doc_id && d.chunk_count > 0);
      if (doc) return doc.doc_id;
    }
  }
  return null;
}

// Chú thích hình lấy từ các dòng "Figure N. …" trong nội dung đoạn (thứ tự trùng thứ tự ảnh của đoạn).
export function figureCaptions(content) {
  return (content || '').split('\n').map((line) => line.trim()).filter((line) => /^(Figure|Fig\.|Hình)\s*\d+/i.test(line));
}
