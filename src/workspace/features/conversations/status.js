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

/**
 * Bộ lọc trạng thái (Q14): Hoàn tất, Chuyển nhân viên, Bị chặn, Lỗi; "Đã ngắt" không có trong bộ lọc.
 * "Chuyển nhân viên" chỉ có ở kênh Website: chọn kênh CRM thì mục này bị khoá.
 */
export function statusFilterOptions(channel) {
  return [
    { value: '', label: S.conv.all },
    { value: 'completed', label: S.status.completed },
    { value: 'handoff', label: channel === 'crm' ? `${S.status.handoff} (${S.conv.handoffCrmNote})` : S.status.handoff, disabled: channel === 'crm' },
    { value: 'blocked', label: S.status.blocked },
    { value: 'error', label: S.status.error },
  ];
}

export const CHANNEL_FILTER_OPTIONS = [
  { value: '', label: S.conv.all },
  { value: 'website', label: S.channel.website },
  { value: 'crm', label: S.channel.crm },
];

/**
 * Bộ lọc Model sản phẩm (Q16): 7 mục, giá trị là mã registry. Tạm khai báo ở đây theo mock đã duyệt;
 * thay bằng GET /chatbot/product-models?for=conversation_filter khi có B8 (FRONTEND_REQUIREMENTS 19.10).
 */
export const PRODUCT_MODEL_OPTIONS = [
  { value: '', label: S.conv.all },
  { value: 'F54', label: 'F54' },
  { value: 'F86', label: 'F86' },
  { value: 'F10T', label: 'F10T' },
  { value: '10S', label: 'Astro 10S' },
  { value: '6AH', label: 'Astro 6AH' },
  { value: '6AV', label: 'Astro 6AV' },
  { value: '10i', label: 'Astro 10i' },
];
