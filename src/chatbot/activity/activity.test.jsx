import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import ActivityTimeline from './ActivityTimeline.jsx';
import { applyStatus, describeStep, guessLanguage, summarize } from './activityModel.js';

const run = (events, start = 1000) => events.reduce((steps, event, i) => applyStatus(steps, event, start + i * 100), []);

describe('activityModel', () => {
    it('ngôn ngữ theo câu hỏi: có dấu tiếng Việt là vi, còn lại en', () => {
        expect(guessLanguage('Cấu hình EtherCAT F54')).toBe('vi');
        expect(guessLanguage('dau noi F54')).toBe('en');
        expect(guessLanguage('What is F86?')).toBe('en');
    });

    it('gộp event theo id, bỏ event sai dạng, giữ thời điểm bắt đầu và kết thúc', () => {
        const steps = run([
            { id: 'security', step: 'security', state: 'running' },
            { id: 'security', step: 'security', state: 'done' },
            { step: 'unknown', state: 'running' },
            null,
            { id: 'r:F54', step: 'retrieval', state: 'running', target: 'F54' },
            { id: 'r:F54', step: 'retrieval', state: 'done', count: 4, score: 0.75, docs: ['F54 Operation Guide'] },
        ]);
        expect(steps.map((s) => [s.id, s.state])).toEqual([['security', 'done'], ['r:F54', 'done']]);
        expect(steps[0].startedAt).toBe(1000);
        expect(steps[0].endedAt).toBe(1100);
        const d = describeStep(steps[1], 'vi');
        expect(d.label).toBe('Tìm trong tài liệu F54');
        expect(d.detail).toBe('Tìm thấy 4 đoạn · độ khớp cao nhất 7,5/10');
        expect(d.chips).toEqual([{ text: 'F54 Operation Guide', kind: 'doc' }]);
        expect(describeStep({ ...steps[1], state: 'running' }, 'en').label).toBe('Searching F54 documents…');
    });

    it('CRM: lần thử lại, lỗi quyền dùng câu dễ hiểu, tên dữ liệu nghiệp vụ là chip', () => {
        const steps = run([
            { id: 'a', step: 'analysis', state: 'done', intent: 'report.count', models: ['F54'] },
            { id: 't1', step: 'tool', state: 'done', tool: 'crm_schema', entities: ['Phiếu bảo hành', 'Thiết bị'] },
            { id: 't2', step: 'tool', state: 'retry', tool: 'crm_query', entities: ['Phiếu bảo hành'], code: 'tool_invalid_args' },
            { id: 't3', step: 'tool', state: 'done', tool: 'crm_query', entities: ['Phiếu bảo hành'], rows: 3 },
            { id: 't4', step: 'tool', state: 'error', tool: 'crm_query', entities: ['Đơn hàng'], code: 'crm_forbidden' },
        ]);
        expect(describeStep(steps[0], 'vi')).toMatchObject({ label: 'Hiểu câu hỏi', detail: 'Báo cáo số liệu', chips: [{ text: 'F54', kind: 'model' }] });
        expect(describeStep(steps[1], 'vi').chips.map((c) => c.text)).toEqual(['Phiếu bảo hành', 'Thiết bị']);
        expect(describeStep(steps[2], 'vi', 1)).toMatchObject({ label: 'Lấy dữ liệu phiếu bảo hành', detail: 'Truy vấn chưa đúng, AI đã tự sửa' });
        expect(describeStep(steps[3], 'vi', 2)).toMatchObject({ label: 'Lấy dữ liệu phiếu bảo hành (lần 2)', detail: 'Nhận 3 dòng dữ liệu' });
        expect(describeStep(steps[4], 'vi').detail).toMatch(/không có quyền xem/);
        expect(summarize(steps, 'done', 'vi', 9800)).toEqual({ text: 'Đã xử lý 5 bước · 9,8 giây · 1 lần tự sửa · 1 lỗi', tone: 'error' });
    });

    it('tóm tắt theo pha: đang chạy, đang trả lời, xong có cảnh báo, đã dừng', () => {
        const steps = run([
            { id: 's', step: 'security', state: 'done' },
            { id: 'r', step: 'retrieval', state: 'warn', count: 0, target: 'F54' },
            { id: 'c', step: 'compose', state: 'running' },
        ]);
        expect(summarize(steps, 'live', 'vi', 0).text).toBe('Đang soạn câu trả lời…');
        expect(summarize(steps, 'answering', 'en', 0).text).toBe('Answering · 3 steps');
        expect(summarize(steps, 'done', 'vi', 4100)).toEqual({ text: 'Đã xử lý 3 bước · 4,1 giây · không thấy tài liệu', tone: 'warn' });
        expect(summarize(steps, 'stopped', 'vi', 0).text).toBe('Đã dừng sau 2 bước');
        expect(describeStep(steps[1], 'vi').detail).toBe('Không có đoạn nào đủ khớp');
    });
});

describe('ActivityTimeline', () => {
    const steps = run([
        { id: 's', step: 'security', state: 'done' },
        { id: 'a', step: 'analysis', state: 'done', intent: 'guide.configuration', models: ['F54'] },
        { id: 'r', step: 'retrieval', state: 'done', count: 4, score: 0.75, target: 'F54' },
        { id: 'c', step: 'compose', state: 'done', count: 2 },
    ]);

    it('đang chạy: thẻ mở, tiêu đề là bước hiện tại', () => {
        const live = applyStatus(steps.slice(0, 2), { id: 'r', step: 'retrieval', state: 'running', target: 'F54' }, Date.now());
        render(<ActivityTimeline activity={{ steps: live, phase: 'live', lang: 'vi', startedAt: Date.now() }} fallbackText="Đang soạn câu trả lời…" />);
        expect(screen.getAllByText('Đang tìm trong tài liệu F54…')).toHaveLength(2); // tiêu đề + dòng bước
        expect(screen.queryByRole('button')).toBeNull();
    });

    it('xong: thu gọn một dòng, bấm để mở lại', () => {
        render(<ActivityTimeline activity={{ steps, phase: 'done', lang: 'vi', startedAt: 0, endedAt: 6200 }} fallbackText="" />);
        const toggle = screen.getByRole('button', { name: /Đã xử lý 4 bước · 6,2 giây/ });
        expect(toggle.getAttribute('aria-expanded')).toBe('false');
        fireEvent.click(toggle);
        expect(toggle.getAttribute('aria-expanded')).toBe('true');
        expect(screen.getByText('Tìm thấy 4 đoạn · độ khớp cao nhất 7,5/10')).toBeTruthy();
    });

    it('xong có cảnh báo thì mở sẵn; chưa có event nào thì hiện "Đang bắt đầu…"', () => {
        const warn = applyStatus(steps, { id: 'r', step: 'retrieval', state: 'warn', count: 0 }, 5000);
        const { unmount } = render(<ActivityTimeline activity={{ steps: warn, phase: 'done', lang: 'vi', startedAt: 0, endedAt: 4100 }} fallbackText="" />);
        expect(screen.getByRole('button', { name: /không thấy tài liệu/ }).getAttribute('aria-expanded')).toBe('true');
        unmount();
        render(<ActivityTimeline activity={{ steps: [], phase: 'live', lang: 'vi', startedAt: Date.now() }} fallbackText="Đang soạn câu trả lời…" />);
        expect(screen.getByText('Đang bắt đầu…')).toBeTruthy();
    });
});
