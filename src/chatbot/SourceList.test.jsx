import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import i18n from '../i18n.js';
import Markdown from '../components/Markdown.jsx';
import { Citation } from './SourceList.jsx';

const SOURCES = [{ source_id: 'S1', title: 'F54 Operation Guide', pages: '41–42', images: [] }];

describe('Huy hiệu trích dẫn của widget', () => {
  it('[S1] thành số tròn; di chuột hoặc Tab tới thì hiện tiêu đề và trang, rời thì ẩn', async () => {
    await i18n.changeLanguage('vi');
    render(<Markdown text="Homing [S1], xem thêm [S9]." renderCitation={(id) => <Citation key={id} id={id} sources={SOURCES} />} />);
    const badge = screen.getByRole('button', { name: 'Nguồn S1: F54 Operation Guide · tr. 41–42' });
    expect(badge.textContent).toBe('1');
    expect(screen.queryByRole('tooltip')).toBeNull();

    fireEvent.mouseEnter(badge);
    expect(screen.getByRole('tooltip').textContent).toBe('F54 Operation Guide · tr. 41–42');
    fireEvent.mouseLeave(badge);
    expect(screen.queryByRole('tooltip')).toBeNull();

    // Nguồn không có trong event `sources` (vd lịch sử tải lại): chỉ có mã nguồn.
    const unknown = screen.getByRole('button', { name: 'Nguồn S9: Nguồn S9' });
    fireEvent.focus(unknown);
    expect(screen.getByRole('tooltip').textContent).toBe('Nguồn S9');
  });
});
