import { Link } from 'react-router-dom';
import { SearchX } from 'lucide-react';
import { S } from '../strings.vi.js';
import { EmptyState } from '../components/ui.jsx';
import styles from './pages.module.css';

export default function NotFoundPage() {
  return (
    <div className={styles.center}>
      <EmptyState icon={SearchX} title={S.pages.notFoundTitle} body={S.pages.notFoundBody} action={<Link to="/conversations">{S.pages.backHome}</Link>} />
    </div>
  );
}
