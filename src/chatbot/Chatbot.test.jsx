import { beforeAll, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';

vi.mock('../services/chatbot.service.js', () => ({
    getWidgetHistory: vi.fn(async () => ({ messages: [] })),
    streamChatbotResponse: vi.fn(),
    streamCrmChatbotResponse: vi.fn(),
}));

// Web Speech API giả: trình duyệt có hỗ trợ thì widget hiện nút micro.
class FakeRecognition {
    static last = null;
    constructor() { FakeRecognition.last = this; }
    start() {}
    stop() { this.onend?.(); }
    abort() { this.onend?.(); }
}

let Chatbot;
let service;
beforeAll(async () => {
    window.webkitSpeechRecognition = FakeRecognition;
    await import('../i18n.js').then((m) => m.default.changeLanguage('vi'));
    Chatbot = (await import('./Chatbot.jsx')).default;
    service = await import('../services/chatbot.service.js');
});

describe('Widget · dòng hoạt động AI và giọng nói (WU-17 đợt 3A)', () => {
    it('event status hiện từng bước; có chữ đầu tiên thì thu gọn; xong ghi tổng số bước', async () => {
        let resolve;
        let handlers;
        service.streamChatbotResponse.mockImplementation((message, options) => {
            handlers = options;
            return new Promise((r) => { resolve = r; });
        });
        render(<Chatbot closeWinChatbot={() => {}} />);
        await act(async () => {}); // chờ lịch sử (rỗng) tải xong
        fireEvent.change(screen.getByLabelText('Tin nhắn của bạn'), { target: { value: 'Cấu hình EtherCAT trên F54' } });
        fireEvent.submit(screen.getByLabelText('Tin nhắn của bạn').closest('form'));
        expect(await screen.findByText('Đang bắt đầu…')).toBeTruthy();

        act(() => {
            handlers.onStatus({ id: 's', step: 'security', state: 'done' });
            handlers.onStatus({ id: 'r', step: 'retrieval', state: 'running', target: 'F54' });
        });
        expect(screen.getAllByText('Đang tìm trong tài liệu F54…').length).toBeGreaterThan(0);

        act(() => {
            handlers.onStatus({ id: 'r', step: 'retrieval', state: 'done', target: 'F54', count: 4, score: 0.75 });
            handlers.onChunk('Vào **Setting**');
        });
        const summary = screen.getByRole('button', { name: /Đang trả lời · 2 bước/ });
        expect(summary.getAttribute('aria-expanded')).toBe('false');

        await act(async () => { resolve(); });
        expect(screen.getByRole('button', { name: /^Đã xử lý 2 bước/ })).toBeTruthy();
        expect(screen.getByText('Setting').tagName).toBe('STRONG');
    });

    it('nút micro: bấm để nghe, chữ nhận được vào ô nhập (không tự gửi), bấm lần nữa để dừng', async () => {
        service.streamChatbotResponse.mockReset();
        render(<Chatbot closeWinChatbot={() => {}} />);
        const mic = await screen.findByRole('button', { name: 'Nói để nhập câu hỏi' });
        fireEvent.click(mic);
        expect(screen.getByRole('button', { name: 'Dừng nghe' }).getAttribute('aria-pressed')).toBe('true');
        act(() => {
            FakeRecognition.last.onresult({ results: [[{ transcript: 'sơ đồ đấu dây F54' }]] });
        });
        expect(screen.getByLabelText('Tin nhắn của bạn').value).toBe('sơ đồ đấu dây F54');
        fireEvent.click(screen.getByRole('button', { name: 'Dừng nghe' }));
        expect(screen.getByRole('button', { name: 'Nói để nhập câu hỏi' })).toBeTruthy();
        expect(service.streamChatbotResponse).not.toHaveBeenCalled();
    });
});
