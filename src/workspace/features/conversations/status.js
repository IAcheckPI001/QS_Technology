// Trạng thái lượt/hội thoại → nhãn và tông màu (Q13, Q14; màu trạng thái giữ nguyên, Q21).

import { S } from '../../strings.vi.js';

const TONE = { completed: 'success', error: 'danger', blocked: 'warning', cancelled: 'neutral', handoff: 'info' };

export function statusLabel(status) {
  return S.status[status] || status || '—';
}

export function statusTone(status) {
  return TONE[status] || 'neutral';
}

export function statusNote(status) {
  return S.statusNote[status] || '';
}

export function channelLabel(channel) {
  return S.channel[channel] || channel || '—';
}

/** Bộ lọc trạng thái trước B2: API nhận completed | blocked | error | cancelled; "Đã ngắt" không có trong bộ lọc (Q14). */
export const STATUS_FILTER_OPTIONS = [
  { value: '', label: S.conv.all },
  { value: 'completed', label: S.status.completed },
  { value: 'blocked', label: S.status.blocked },
  { value: 'error', label: S.status.error },
];
