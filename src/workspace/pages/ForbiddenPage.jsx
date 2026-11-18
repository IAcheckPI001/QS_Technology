import { Link } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';
import { S } from '../strings.vi.js';
import { EmptyState } from '../components/ui.jsx';
import styles from './pages.module.css';

export default function ForbiddenPage() {
  return (
    <div className={styles.center}>
      <EmptyState icon={ShieldAlert} title={S.pages.forbiddenTitle} body={S.pages.forbiddenBody} action={<Link to="/conversations">{S.pages.backHome}</Link>} />
    </div>
  );
}
