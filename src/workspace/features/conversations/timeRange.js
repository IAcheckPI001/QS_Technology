// Bộ lọc Thời gian (Q19): ngày tính theo giờ Việt Nam (UTC+7), gửi máy chủ `from`/`to` dạng YYYY-MM-DD,
// tính cả hai đầu. Kiểm tra giống máy chủ (`conversation_filters.date_range`).

import { S } from '../../strings.vi.js';

export const TIME_PRESETS = ['today', '7d', '30d', 'month'];
export const DEFAULT_TIME = '7d';
export const MAX_RANGE_DAYS = 366;

const DAY_MS = 86_400_000;
const VN_OFFSET_MS = 7 * 3_600_000;

/** Ngày hôm nay theo giờ Việt Nam, dạng YYYY-MM-DD. */
export function vnToday(now = Date.now()) {
  return new Date(now + VN_OFFSET_MS).toISOString().slice(0, 10);
}

const toDate = (iso) => new Date(`${iso}T00:00:00Z`);
const toIso = (date) => date.toISOString().slice(0, 10);

export function addDays(iso, days) {
  return toIso(new Date(toDate(iso).getTime() + days * DAY_MS));
}

export function daysBetween(from, to) {
  return Math.round((toDate(to) - toDate(from)) / DAY_MS) + 1;
}

const monthStart = (iso) => `${iso.slice(0, 8)}01`;

/** Khoảng {from, to} của một lựa chọn có sẵn. */
export function presetRange(preset, today = vnToday()) {
  switch (preset) {
    case 'today':
      return { from: today, to: today };
    case '30d':
      return { from: addDays(today, -29), to: today };
    case 'month':
      return { from: monthStart(today), to: today };
    case '7d':
    default:
      return { from: addDays(today, -6), to: today };
  }
}

/** Nút nhanh trong bảng chọn khoảng (Q19). */
export function quickRanges(today = vnToday()) {
  const yesterday = addDays(today, -1);
  const weekday = (toDate(today).getUTCDay() + 6) % 7; // Thứ Hai = 0
  const lastMonthEnd = addDays(monthStart(today), -1);
  return [
    { label: S.conv.time.today, from: today, to: today },
    { label: S.conv.time.yesterday, from: yesterday, to: yesterday },
    { label: S.conv.time.thisWeek, from: addDays(today, -weekday), to: today },
    { label: S.conv.time.thisMonth, from: monthStart(today), to: today },
    { label: S.conv.time.lastMonth, from: monthStart(lastMonthEnd), to: lastMonthEnd },
  ];
}

/** Lỗi của khoảng tuỳ chọn, hoặc null khi hợp lệ. */
export function rangeError(from, to, today = vnToday()) {
  if (!from || !to) return S.conv.time.errMissing;
  if (from > to) return S.conv.time.errOrder;
  if (to > today) return S.conv.time.errFuture;
  if (daysBetween(from, to) > MAX_RANGE_DAYS) return S.conv.time.errTooLong(MAX_RANGE_DAYS);
  return null;
}

/** Khoảng đang lọc từ bộ lọc trên URL; khoảng tuỳ chọn sai thì về mặc định. */
export function activeRange(filters, today = vnToday()) {
  if (filters.time === 'custom' && !rangeError(filters.from, filters.to, today)) {
    return { from: filters.from, to: filters.to, custom: true };
  }
  const preset = TIME_PRESETS.includes(filters.time) ? filters.time : DEFAULT_TIME;
  return { ...presetRange(preset, today), custom: false, preset };
}

export const formatIsoDate = (iso) => `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}`;
