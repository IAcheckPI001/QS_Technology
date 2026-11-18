// Tô sáng các từ của `query` trong `text` (khớp không dấu, giữ chữ gốc).

import { highlightParts } from '../utils/search.js';

export default function Highlight({ text, query }) {
  const parts = highlightParts(text, query);
  if (parts.length === 1 && !parts[0].hit) return text;
  return parts.map((part, index) => (part.hit ? <mark key={index}>{part.text}</mark> : part.text));
}
