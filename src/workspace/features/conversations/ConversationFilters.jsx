// Bộ lọc Lịch sử hội thoại (mock Conversations / MobileConversations; Q14, Q16, Q19).
// - Máy tính: ô tìm + 4 ô chọn trên một hàng; "Tuỳ chọn…" mở bảng chọn khoảng ngay dưới ô Thời gian,
//   bấm ra ngoài hoặc Esc = Huỷ. Khoảng đang lọc hiện thẻ "Từ … đến … · n ngày" có Sửa và ×.
// - Điện thoại (≤ 720px): ô tìm + hàng chip ("Bộ lọc · n", khoảng thời gian, các bộ lọc đang dùng có ×);
//   bấm chip mở sheet chỉnh nháp, "Xem n hội thoại" mới áp dụng.

import { useEffect, useRef, useState } from 'react';
import { SlidersHorizontal, X } from 'lucide-react';
import { conversationsApi } from '../../api/conversations.js';
import Modal from '../../components/Modal.jsx';
import { Button, Card, SelectField, TextField } from '../../components/ui.jsx';
import { useResource } from '../../hooks/useResource.js';
import { S } from '../../strings.vi.js';
import { CHANNEL_FILTER_OPTIONS, PRODUCT_MODEL_OPTIONS, statusFilterOptions } from './status.js';
import { DEFAULT_TIME, TIME_PRESETS, activeRange, daysBetween, formatIsoDate, quickRanges, rangeError } from './timeRange.js';
import { channelPatch, periodShort, toApiFilters } from './filterModel.js';
import styles from './conversations.module.css';

// ---- Máy tính -------------------------------------------------------------------------------------

export function DesktopFilters({ filters, setFilters, query, setQuery, range, today, rangeOpen, setRangeOpen }) {
  const status = toApiFilters(filters, today).status;
  return (
    <Card className={styles.filters} aria-label={S.conv.filters}>
      <TextField
        className={styles.searchField}
        type="search"
        label={S.conv.search}
        placeholder={S.conv.searchPlaceholder}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <SelectField
        className={styles.selectField}
        label={S.conv.channelFilter}
        value={filters.channel}
        options={CHANNEL_FILTER_OPTIONS}
        onChange={(event) => setFilters(channelPatch(filters, event.target.value))}
      />
      <SelectField
        className={styles.selectField}
        label={S.conv.statusLabel}
        value={status}
        options={statusFilterOptions(filters.channel)}
        onChange={(event) => setFilters({ status: event.target.value })}
      />
      <SelectField
        className={styles.selectField}
        label={S.conv.modelFilter}
        value={filters.model}
        options={PRODUCT_MODEL_OPTIONS}
        onChange={(event) => setFilters({ model: event.target.value })}
      />
      <TimeFilter range={range} today={today} setFilters={setFilters} open={rangeOpen} setOpen={setRangeOpen} />
    </Card>
  );
}

function TimeFilter({ range, today, setFilters, open, setOpen }) {
  const options = [
    ...TIME_PRESETS.map((value) => ({ value, label: S.conv.time[value] })),
    { value: 'custom', label: range.custom ? S.conv.time.customValue(periodShort(range)) : S.conv.time.custom },
  ];
  const onSelect = (event) => {
    const value = event.target.value;
    if (value === 'custom') setOpen(true);
    else setFilters({ time: value, from: '', to: '' });
  };
  return (
    <div className={styles.timeWrap}>
      <SelectField
        className={styles.timeField}
        label={S.conv.time.label}
        value={range.custom ? 'custom' : range.preset}
        options={options}
        onChange={onSelect}
        aria-expanded={open}
        aria-controls="range-panel"
      />
      {open && (
        <RangePanel
          range={range}
          today={today}
          onCancel={() => setOpen(false)}
          onApply={(from, to) => {
            setFilters({ time: 'custom', from, to });
            setOpen(false);
          }}
        />
      )}
    </div>
  );
}

function RangePanel({ range, today, onCancel, onApply }) {
  const [draft, setDraft] = useState({ from: range.from, to: range.to });
  const panelRef = useRef(null);
  const error = rangeError(draft.from, draft.to, today);

  useEffect(() => {
    panelRef.current?.querySelector('input')?.focus();
  }, []);

  return (
    <>
      {/* Lớp nền trong suốt: bấm ra ngoài bảng = Huỷ (mock). */}
      <div className={styles.rangeBackdrop} aria-hidden="true" onMouseDown={onCancel} />
      <div
        id="range-panel"
        ref={panelRef}
        role="dialog"
        aria-labelledby="range-title"
        className={styles.rangePanel}
        onKeyDown={(event) => {
          if (event.key === 'Escape') onCancel();
        }}
      >
        <div className={styles.rangeHead}>
          <h2 id="range-title" className={styles.rangeTitle}>{S.conv.time.panelTitle}</h2>
          <span className={styles.rangeTz}>{S.conv.time.panelTz}</span>
        </div>
        <div className={styles.quick}>
          {quickRanges(today).map((item) => (
            <button
              key={item.label}
              type="button"
              className={styles.quickButton}
              aria-pressed={draft.from === item.from && draft.to === item.to}
              onClick={() => setDraft({ from: item.from, to: item.to })}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className={styles.rangeInputs}>
          <TextField type="date" label={S.conv.time.from} value={draft.from} max={today} onChange={(event) => setDraft((d) => ({ ...d, from: event.target.value }))} />
          <TextField type="date" label={S.conv.time.to} value={draft.to} max={today} onChange={(event) => setDraft((d) => ({ ...d, to: event.target.value }))} />
        </div>
        {error && <p className={styles.rangeError} role="alert">{error}</p>}
        <p className={styles.rangeNote}>{S.conv.time.panelNote}</p>
        <div className={styles.rangeActions}>
          <Button onClick={onCancel}>{S.conv.time.cancel}</Button>
          <Button variant="primary" onClick={() => !error && onApply(draft.from, draft.to)} disabled={Boolean(error)}>{S.conv.time.apply}</Button>
        </div>
      </div>
    </>
  );
}

/** Thẻ khoảng đang lọc (máy tính): "Từ … đến … · n ngày" + Sửa + ×. */
export function RangeChip({ range, onEdit, onClear }) {
  return (
    <div className={styles.chipRow}>
      <span>{S.conv.time.filtering}</span>
      <span className={styles.chip}>
        {S.conv.time.chip(formatIsoDate(range.from), formatIsoDate(range.to), daysBetween(range.from, range.to))}
        <button type="button" className={styles.chipEdit} onClick={onEdit}>{S.conv.time.edit}</button>
        <button type="button" className={styles.chipButton} aria-label={S.conv.time.clear} onClick={onClear}>
          <X size={16} aria-hidden="true" />
        </button>
      </span>
    </div>
  );
}

// ---- Điện thoại -------------------------------------------------------------------------------------

const labelOf = (options, value) => options.find((option) => option.value === value)?.label || value;

export function MobileFilters({ filters, setFilters, query, setQuery, range, today }) {
  const [open, setOpen] = useState(false);
  const status = toApiFilters(filters, today).status;
  const active = [
    filters.channel && { key: 'channel', label: labelOf(CHANNEL_FILTER_OPTIONS, filters.channel), patch: { channel: '' } },
    status && { key: 'status', label: labelOf(statusFilterOptions(''), status), patch: { status: '' } },
    filters.model && { key: 'model', label: labelOf(PRODUCT_MODEL_OPTIONS, filters.model), patch: { model: '' } },
  ].filter(Boolean);

  return (
    <div className={styles.mobileFilters}>
      <TextField
        type="search"
        label={S.conv.search}
        className={styles.mobileSearch}
        placeholder={S.conv.searchPlaceholderShort}
        value={query}
        onChange={(event) => setQuery(event.target.value)}
      />
      <div className={styles.chips} role="group" aria-label={S.conv.activeFilters}>
        <button type="button" className={`${styles.filterChip} ${active.length ? styles.filterChipOn : ''}`} onClick={() => setOpen(true)}>
          <SlidersHorizontal size={16} aria-hidden="true" />
          {active.length ? S.conv.filterCount(active.length) : S.conv.filters}
        </button>
        <button type="button" className={`${styles.filterChip} ${styles.filterChipOn}`} onClick={() => setOpen(true)}>
          {periodShort(range)}
        </button>
        {active.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`${styles.filterChip} ${styles.filterChipOn}`}
            aria-label={S.conv.clearFilter(item.label)}
            onClick={() => setFilters(item.patch)}
          >
            {item.label}
            <X size={14} aria-hidden="true" />
          </button>
        ))}
      </div>
      {open && <FilterSheet filters={filters} today={today} onClose={() => setOpen(false)} onApply={(patch) => { setFilters(patch); setOpen(false); }} />}
    </div>
  );
}

const SHEET_COUNT_DELAY = 300;

function FilterSheet({ filters, today, onClose, onApply }) {
  const initialRange = activeRange(filters, today);
  const [draft, setDraft] = useState({
    channel: filters.channel,
    status: toApiFilters(filters, today).status,
    model: filters.model,
    time: initialRange.custom ? 'custom' : initialRange.preset,
    from: initialRange.from,
    to: initialRange.to,
  });
  const patchDraft = (patch) => setDraft((current) => ({ ...current, ...patch }));
  const error = draft.time === 'custom' ? rangeError(draft.from, draft.to, today) : null;
  const draftFilters = { ...filters, ...draft, from: draft.time === 'custom' ? draft.from : '', to: draft.time === 'custom' ? draft.to : '' };

  // "Xem n hội thoại": số hội thoại khớp bộ lọc nháp (chờ 300 ms sau lần chỉnh cuối).
  const [countKey, setCountKey] = useState(() => JSON.stringify(toApiFilters(draftFilters, today)));
  const nextKey = error ? null : JSON.stringify(toApiFilters(draftFilters, today));
  useEffect(() => {
    if (!nextKey || nextKey === countKey) return undefined;
    const timer = setTimeout(() => setCountKey(nextKey), SHEET_COUNT_DELAY);
    return () => clearTimeout(timer);
  }, [nextKey, countKey]);
  const count = useResource(({ signal }) => conversationsApi.metrics(JSON.parse(countKey), { signal }), [countKey]);
  const settled = !count.loading && nextKey === countKey;
  const applyLabel = settled && count.data ? S.conv.sheetApply(count.data.conversation_count) : S.conv.time.apply;

  const reset = () => setDraft({ channel: '', status: '', model: '', time: DEFAULT_TIME, from: '', to: '' });
  const apply = () => {
    if (error) return;
    onApply({
      channel: draft.channel,
      status: draft.channel === 'crm' && draft.status === 'handoff' ? '' : draft.status,
      model: draft.model,
      time: draft.time,
      from: draft.time === 'custom' ? draft.from : '',
      to: draft.time === 'custom' ? draft.to : '',
    });
  };

  const toggle = (group, options, value, onPick) => (
    <div className={styles.sheetGroup} role="group" aria-labelledby={`sheet-${group}`}>
      <h3 id={`sheet-${group}`} className={styles.sheetGroupTitle}>{S.conv.sheetGroup[group]}</h3>
      <div className={styles.wrap}>
        {options.map((option) => (
          <button
            key={option.value || 'all'}
            type="button"
            className={styles.filterChip}
            aria-pressed={value === option.value}
            disabled={option.disabled}
            onClick={() => onPick(option.value)}
          >
            {option.short || option.label}
          </button>
        ))}
      </div>
    </div>
  );

  const timeOptions = [...TIME_PRESETS, 'custom'].map((value) => ({ value, label: value === 'custom' ? S.conv.time.customShort : S.conv.time[value] }));
  const statusOptions = statusFilterOptions(draft.channel).map((option) => ({ ...option, short: option.value === 'handoff' ? S.status.handoff : option.label }));

  return (
    <Modal
      open
      onClose={onClose}
      title={S.conv.filters}
      footer={(
        <>
          <Button onClick={reset}>{S.conv.sheetReset}</Button>
          <Button variant="primary" onClick={apply} disabled={Boolean(error)}>{applyLabel}</Button>
        </>
      )}
    >
      <div className={styles.sheetBody}>
        {toggle('time', timeOptions, draft.time, (time) => patchDraft(time === 'custom' && draft.time !== 'custom' ? { time, from: draft.from, to: draft.to } : { time }))}
        {draft.time === 'custom' && (
          <div className={styles.sheetRange}>
            <TextField type="date" label={S.conv.time.from} value={draft.from} max={today} onChange={(event) => patchDraft({ from: event.target.value })} />
            <TextField type="date" label={S.conv.time.to} value={draft.to} max={today} onChange={(event) => patchDraft({ to: event.target.value })} />
            {error && <p className={styles.rangeError} role="alert">{error}</p>}
            <p className={styles.rangeNote}>{S.conv.time.sheetNote}</p>
          </div>
        )}
        {toggle('channel', CHANNEL_FILTER_OPTIONS, draft.channel, (channel) => patchDraft(channel === 'crm' && draft.status === 'handoff' ? { channel, status: '' } : { channel }))}
        {toggle('status', statusOptions, draft.status, (status) => patchDraft({ status }))}
        {draft.channel === 'crm' && <p className={styles.rangeNote}>{S.conv.handoffWebsiteOnly}</p>}
        <SelectField
          label={S.conv.modelFilter}
          value={draft.model}
          options={PRODUCT_MODEL_OPTIONS}
          onChange={(event) => patchDraft({ model: event.target.value })}
        />
      </div>
    </Modal>
  );
}
