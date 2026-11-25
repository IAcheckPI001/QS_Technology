import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import Markdown from './Markdown.jsx';
import { linkCitations } from './markdownCitations.js';

describe('linkCitations', () => {
  it('đổi [S1] thành link nội bộ, giữ nguyên trong code', () => {
    expect(linkCitations('Xem [S1][S12].')).toBe('Xem [S1](#cite-S1)[S12](#cite-S12).');
    expect(linkCitations('`[S1]` và\n```\n[S2]\n```\n[S3]')).toBe('`[S1]` và\n```\n[S2]\n```\n[S3](#cite-S3)');
    expect(linkCitations(null)).toBe('');
  });
});

describe('Markdown', () => {
  it('render tiêu đề, bảng GFM, danh sách, trích dẫn và code; không hiện cú pháp thô', () => {
    const text = [
      '### Cách sử dụng bộ điều khiển F86',
      '',
      '**Đậm** và *nghiêng*.',
      '',
      '| Thông số | F54 |',
      '|---|---|',
      '| Số trục | 4 |',
      '',
      '1. Một',
      '2. Hai',
      '',
      '> Lưu ý',
      '',
      '`G28`',
    ].join('\n');
    const { container } = render(<Markdown text={text} />);
    expect(screen.getByRole('heading', { level: 3, name: 'Cách sử dụng bộ điều khiển F86' })).toBeTruthy();
    expect(screen.getByRole('table')).toBeTruthy();
    expect(screen.getByRole('columnheader', { name: 'Thông số' })).toBeTruthy();
    expect(screen.getByRole('cell', { name: '4' })).toBeTruthy();
    expect(container.querySelector('strong').textContent).toBe('Đậm');
    expect(container.querySelector('em').textContent).toBe('nghiêng');
    expect(container.querySelectorAll('ol li')).toHaveLength(2);
    expect(container.querySelector('blockquote').textContent.trim()).toBe('Lưu ý');
    expect(container.querySelector('code').textContent).toBe('G28');
    expect(container.textContent).not.toContain('###');
    expect(container.textContent).not.toContain('|---');
  });

  it('link http mở tab mới; link javascript: và HTML thô không được render', () => {
    const { container } = render(<Markdown text={'[Tài liệu](https://qstcnc.com/a) [xấu](javascript:alert(1)) <b>thô</b>'} />);
    const link = screen.getByRole('link', { name: 'Tài liệu' });
    expect(link.getAttribute('target')).toBe('_blank');
    expect(link.getAttribute('rel')).toBe('noopener noreferrer');
    expect(screen.queryByRole('link', { name: 'xấu' })).toBeNull();
    expect(container.querySelector('b')).toBeNull();
  });

  it('[S1] thành huy hiệu tròn; renderCitation thay được huy hiệu', () => {
    const { rerender } = render(<Markdown text="Homing [S1]." />);
    expect(screen.getByLabelText('Nguồn S1').textContent).toBe('1');
    expect(screen.queryByText(/\[S1\]/)).toBeNull();
    rerender(<Markdown text="Homing [S2]." renderCitation={(id) => <button key={id} type="button">{`nút ${id}`}</button>} />);
    expect(screen.getByRole('button', { name: 'nút S2' })).toBeTruthy();
  });
});
