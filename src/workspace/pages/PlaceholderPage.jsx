// Màn chưa dựng (GĐ 0): nói rõ là chưa hoạt động, không giả làm tính năng (TR-10).

import { Construction } from 'lucide-react';
import { S } from '../strings.vi.js';
import { Card, EmptyState, PageHeader } from '../components/ui.jsx';
import styles from './pages.module.css';

export default function PlaceholderPage({ title, phase }) {
  return (
    <div className={styles.page}>
      <PageHeader title={title} />
      <Card>
        <EmptyState icon={Construction} title={S.pages.placeholderTitle} body={S.pages.placeholderBody(phase)} />
      </Card>
    </div>
  );
}
