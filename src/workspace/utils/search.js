// Tìm không dấu và tô sáng từ khớp (B2, FRONTEND_REQUIREMENTS 19.4 / Q29).
// Cùng quy tắc với máy chủ (`conversation_filters.fold`, `SearchTerms`): chữ thường, bỏ dấu (đ → d),
// tách theo khoảng trắng, bỏ từ dưới 2 ký tự, tối đa 8 từ.

const MIN_TOKEN = 2;
const MAX_TOKENS = 8;

export function foldText(text) {
  return String(text ?? '')
    .toLowerCase()
    .replace(/đ/g, 'd')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '');
}

export function searchTokens(query) {
  const tokens = String(query ?? '')
    .split(/\s+/)
    .map(foldText)
    .filter((token) => token.length >= MIN_TOKEN);
  return [...new Set(tokens)].slice(0, MAX_TOKENS);
}

/** Mọi từ của `query` có trong `text` (không dấu, không cần đúng thứ tự). */
export function matchesAll(text, query) {
  const tokens = searchTokens(query);
  const folded = foldText(text);
  return tokens.length > 0 && tokens.every((token) => folded.includes(token));
}

/**
 * Tách `text` thành các đoạn [{ text, hit }] để tô sáng các từ của `query`, khớp không dấu nhưng giữ
 * nguyên chữ gốc. Không có từ nào khớp thì trả một đoạn duy nhất.
 */
export function highlightParts(text, query) {
  const source = String(text ?? '');
  const tokens = searchTokens(query);
  if (!source || tokens.length === 0) return [{ text: source, hit: false }];

  // Bỏ dấu từng ký tự gốc, nhớ vị trí gốc của từng ký tự sau khi bỏ dấu.
  let folded = '';
  const origin = [];
  for (let i = 0; i < source.length; i += 1) {
    const piece = foldText(source[i]);
    for (let k = 0; k < piece.length; k += 1) {
      folded += piece[k];
      origin.push(i);
    }
  }

  const ranges = [];
  for (const token of tokens) {
    let from = folded.indexOf(token);
    while (from !== -1) {
      ranges.push([origin[from], origin[from + token.length - 1] + 1]);
      from = folded.indexOf(token, from + token.length);
    }
  }
  if (ranges.length === 0) return [{ text: source, hit: false }];

  ranges.sort((a, b) => a[0] - b[0]);
  const merged = [ranges[0]];
  for (const [start, end] of ranges.slice(1)) {
    const last = merged[merged.length - 1];
    if (start <= last[1]) last[1] = Math.max(last[1], end);
    else merged.push([start, end]);
  }

  // Ký tự dấu tổ hợp đứng ngay sau đoạn khớp thuộc về chữ cuối của đoạn.
  for (const range of merged) {
    while (range[1] < source.length && /[̀-ͯ]/.test(source[range[1]])) range[1] += 1;
  }

  const parts = [];
  let cursor = 0;
  for (const [start, end] of merged) {
    if (start > cursor) parts.push({ text: source.slice(cursor, start), hit: false });
    parts.push({ text: source.slice(start, end), hit: true });
    cursor = end;
  }
  if (cursor < source.length) parts.push({ text: source.slice(cursor), hit: false });
  return parts;
}
