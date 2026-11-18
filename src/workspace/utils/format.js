// Định dạng hiển thị. Ngày giờ luôn theo giờ Việt Nam (Q19), số theo kiểu vi-VN (dấu phẩy thập phân).

const TIME_ZONE = 'Asia/Ho_Chi_Minh';
const PARTS = new Intl.DateTimeFormat('en-GB', {
  timeZone: TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
});

function parts(value) {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return Object.fromEntries(PARTS.formatToParts(date).map((part) => [part.type, part.value]));
}

/** "08:40" */
export function formatTime(value) {
  const p = parts(value);
  return p ? `${p.hour}:${p.minute}` : '';
}

/** "17/11 08:40" */
export function formatDayTime(value) {
  const p = parts(value);
  return p ? `${p.day}/${p.month} ${p.hour}:${p.minute}` : '';
}

/** "17/11/2026 08:40" */
export function formatFullDateTime(value) {
  const p = parts(value);
  return p ? `${p.day}/${p.month}/${p.year} ${p.hour}:${p.minute}` : '';
}

/** "17/11/2026" */
export function formatDate(value) {
  const p = parts(value);
  return p ? `${p.day}/${p.month}/${p.year}` : '';
}

/** Cùng ngày (giờ Việt Nam). */
export function sameDay(a, b) {
  return formatDate(a) !== '' && formatDate(a) === formatDate(b);
}

export function formatNumber(value) {
  return Number(value || 0).toLocaleString('vi-VN');
}

/** "124 ms", "4,8 giây" */
export function formatDuration(ms) {
  if (ms === null || ms === undefined || Number.isNaN(Number(ms))) return '—';
  const value = Number(ms);
  if (value < 1000) return `${Math.round(value)} ms`;
  return `${(value / 1000).toLocaleString('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} giây`;
}

/** Cột "Mất" của diễn biến: "124 ms", "2,35 s" */
export function formatDurationShort(ms) {
  if (ms === null || ms === undefined) return '—';
  const value = Number(ms);
  if (value < 1000) return `${value < 10 ? value.toLocaleString('vi-VN', { maximumFractionDigits: 1 }) : Math.round(value)} ms`;
  return `${(value / 1000).toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} s`;
}

/** Chi phí ước tính theo USD (trước B2 chưa có VND theo từng dòng, FRONTEND_REQUIREMENTS 19.4). */
export function formatUsd(value) {
  if (value === null || value === undefined) return '—';
  return `${Number(value).toLocaleString('vi-VN', { maximumFractionDigits: 6 })} USD`;
}

/** Chi phí VND: "335 đ", "< 1 đ" cho số lẻ rất nhỏ. */
export function formatVnd(value) {
  if (value === null || value === undefined) return '—';
  const number = Number(value);
  if (number > 0 && number < 1) return '< 1 đ';
  return `${Math.round(number).toLocaleString('vi-VN')} đ`;
}

/** Độ khớp 0,92 */
export function formatScore(value) {
  if (value === null || value === undefined) return '—';
  return Number(value).toLocaleString('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** Giờ hỏi = created_at − latency_ms (FRONTEND_REQUIREMENTS 19.2 W3); thiếu latency → null. */
export function askedAt(turn) {
  if (!turn || turn.latency_ms === null || turn.latency_ms === undefined) return null;
  const created = new Date(turn.created_at).getTime();
  return Number.isNaN(created) ? null : new Date(created - Number(turn.latency_ms));
}
