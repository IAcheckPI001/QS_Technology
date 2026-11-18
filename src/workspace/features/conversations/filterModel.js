// Bộ lọc Lịch sử hội thoại trên URL → tham số API và nhãn ngắn (dùng chung cho ConversationFilters và trang).

import { S } from '../../strings.vi.js';
import { DEFAULT_TIME, activeRange, formatIsoDate } from './timeRange.js';

export const FILTER_DEFAULTS = { q: '', channel: '', status: '', model: '', time: DEFAULT_TIME, from: '', to: '' };

/** Bộ lọc trên URL → tham số API. Kênh CRM không có trạng thái "Chuyển nhân viên" (Q14). */
export function toApiFilters(filters, today) {
  const range = activeRange(filters, today);
  const status = filters.channel === 'crm' && filters.status === 'handoff' ? '' : filters.status;
  return { q: filters.q.trim(), status, channel: filters.channel, productModel: filters.model, from: range.from, to: range.to };
}

/** Đổi kênh sang CRM thì bỏ luôn trạng thái handoff trên URL (không để bộ lọc ẩn bật lại). */
export function channelPatch(filters, channel) {
  return channel === 'crm' && filters.status === 'handoff' ? { channel, status: '' } : { channel };
}

const shortDate = (iso) => formatIsoDate(iso).slice(0, 5);

/** Nhãn ngắn của khoảng đang lọc (ô chọn, chip điện thoại). */
export function periodShort(range) {
  return range.custom ? `${shortDate(range.from)} – ${shortDate(range.to)}` : S.conv.time[range.preset];
}
