import { describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import Modal from './Modal.jsx';
import ConfirmDialog from './ConfirmDialog.jsx';
import ToastProvider from './toast/ToastProvider.jsx';
import { useToast } from './toast/useToast.js';
import { LoadMore } from './ui.jsx';

function ModalHarness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>Mở</button>
      <Modal open={open} onClose={() => setOpen(false)} title="Tạo khóa" footer={<button type="button">Cuối</button>}>
        <input aria-label="Tên" data-autofocus />
      </Modal>
    </>
  );
}

describe('Modal', () => {
  it('focus vào ô đầu, Esc đóng và trả focus về nút đã mở', () => {
    render(<ModalHarness />);
    const opener = screen.getByText('Mở');
    opener.focus();
    fireEvent.click(opener);
    expect(document.activeElement).toBe(screen.getByLabelText('Tên'));
    fireEvent.keyDown(document.activeElement, { key: 'Escape' });
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(document.activeElement).toBe(opener);
  });

  it('Tab ở phần tử cuối quay về phần tử đầu (giữ focus trong cửa sổ)', () => {
    render(<ModalHarness />);
    fireEvent.click(screen.getByText('Mở'));
    const last = screen.getByText('Cuối');
    last.focus();
    fireEvent.keyDown(last, { key: 'Tab' });
    expect(document.activeElement).toBe(screen.getByLabelText('Đóng'));
  });
});

describe('ConfirmDialog', () => {
  it('khoá nút cho tới khi gõ đúng tên', () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog open title="Thu hồi khóa?" confirmLabel="Thu hồi" requireText="crm-test" onConfirm={onConfirm} onCancel={() => {}} />);
    const confirm = screen.getByText('Thu hồi').closest('button');
    expect(confirm.disabled).toBe(true);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'crm-test' } });
    expect(confirm.disabled).toBe(false);
    fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledWith('');
  });

  it('bắt buộc lý do khi requireReason', () => {
    const onConfirm = vi.fn();
    render(<ConfirmDialog open title="Tắt đoạn?" confirmLabel="Tắt" requireReason onConfirm={onConfirm} onCancel={() => {}} />);
    fireEvent.click(screen.getByText('Tắt').closest('button'));
    expect(onConfirm).not.toHaveBeenCalled();
    expect(screen.getByRole('alert').textContent).toMatch(/lý do/);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: ' trùng nội dung ' } });
    fireEvent.click(screen.getByText('Tắt').closest('button'));
    expect(onConfirm).toHaveBeenCalledWith('trùng nội dung');
  });
});

function ToastHarness({ undo }) {
  const { show } = useToast();
  return (
    <>
      <button type="button" onClick={() => show({ message: 'Đã duyệt', tone: 'success', undo })}>ok</button>
      <button type="button" onClick={() => show({ message: 'Lỗi lưu', tone: 'error' })}>err</button>
    </>
  );
}

describe('Toast', () => {
  it('thành công tự ẩn sau 6 giây, lỗi thì không; Hoàn tác gọi undo', () => {
    vi.useFakeTimers();
    const undo = vi.fn();
    render(<ToastProvider><ToastHarness undo={undo} /></ToastProvider>);
    fireEvent.click(screen.getByText('ok'));
    fireEvent.click(screen.getByText('err'));
    act(() => vi.advanceTimersByTime(6100));
    expect(screen.queryByText('Đã duyệt')).toBeNull();
    expect(screen.getByText('Lỗi lưu')).toBeTruthy();

    fireEvent.click(screen.getByText('ok'));
    fireEvent.click(screen.getByText('Hoàn tác'));
    expect(undo).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });
});

describe('LoadMore', () => {
  it('hiện x / y, nút tải thêm, và "Đã hiển thị hết" khi done', () => {
    const { rerender } = render(<LoadMore count={25} total={312} noun="hội thoại" pageSize={25} onLoadMore={() => {}} />);
    expect(screen.getByText('Đang hiển thị 25 / 312 hội thoại')).toBeTruthy();
    expect(screen.getByText('Tải thêm 25 hội thoại')).toBeTruthy();
    rerender(<LoadMore count={312} total={312} noun="hội thoại" pageSize={25} done onLoadMore={() => {}} />);
    expect(screen.getByText('Đã hiển thị hết')).toBeTruthy();
  });
});
