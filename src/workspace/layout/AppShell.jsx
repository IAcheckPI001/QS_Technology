// Khung app (Q22, mục 17): sidebar desktop + thanh trên/thanh dưới điện thoại + nút chat thử.

import { NavLink, Outlet } from 'react-router-dom';
import { ChevronsLeft, ChevronsRight, LogOut } from 'lucide-react';
import ChatbotWidget from '../../components/ChatbotWidget.jsx';
import logo from '../assets/qs-logo.png';
import { S } from '../strings.vi.js';
import { useAuth } from '../auth/useAuth.js';
import { can, initials } from '../auth/permissions.js';
import { useLocalStorage } from '../hooks/useLocalStorage.js';
import { Button, IconButton } from '../components/ui.jsx';
import { NAV_ITEMS } from './navItems.js';
import styles from './AppShell.module.css';

const navClass = ({ isActive }) => `${styles.navLink} ${isActive ? styles.active : ''}`;
const tabClass = ({ isActive }) => `${styles.tabLink} ${isActive ? styles.tabActive : ''}`;

export default function AppShell() {
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useLocalStorage('ws.sidebarCollapsed', false);
  const items = NAV_ITEMS.filter((item) => can(user, item.permission));
  const name = user?.display_name || user?.email || '';
  const accountTitle = `${name} · ${user?.email || ''}`;

  return (
    <div className={styles.shell}>
      <aside className={`${styles.sidebar} ${collapsed ? styles.collapsed : ''}`} aria-label="Thanh bên">
        <div className={styles.brand}>
          <img src={logo} alt={S.company} className={styles.logo} width="51" height="28" />
          <span className={styles.brandName}>{S.appName}</span>
          <IconButton
            icon={collapsed ? ChevronsRight : ChevronsLeft}
            label={collapsed ? S.nav.expand : S.nav.collapse}
            aria-expanded={!collapsed}
            onClick={() => setCollapsed((value) => !value)}
          />
        </div>
        <nav aria-label={S.nav.label}>
          <ul className={styles.nav}>
            {items.map((item) => {
              const NavIcon = item.icon;
              return (
                <li key={item.to}>
                  <NavLink to={item.to} className={navClass} title={collapsed ? item.label : undefined}>
                    <NavIcon size={20} aria-hidden="true" />
                    <span className={styles.label}>{item.label}</span>
                  </NavLink>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className={styles.account}>
          <span className={styles.avatar} title={collapsed ? accountTitle : undefined} aria-hidden="true">{initials(name)}</span>
          <span className={styles.accountInfo}>
            <strong>{name}</strong>
            <span>{user?.email} · {user?.role}</span>
          </span>
          <Button className={styles.logout} size="small" icon={LogOut} onClick={logout} title={S.account.logout} aria-label={S.account.logout}>
            <span className={styles.logoutText}>{S.account.logout}</span>
          </Button>
        </div>
      </aside>

      <header className={styles.topbar}>
        <img src={logo} alt={S.company} className={styles.logo} width="43" height="24" />
        <span className={styles.topbarName}>{S.appName}</span>
        <IconButton icon={LogOut} label={S.account.logout} onClick={logout} />
      </header>

      <main className={styles.main} id="ws-main">
        <Outlet />
      </main>

      <nav aria-label={S.nav.label}>
        <ul className={styles.tabbar} style={{ '--ws-tabs': items.length }}>
          {items.map((item) => {
            const TabIcon = item.icon;
            return (
              <li key={item.to}>
                <NavLink to={item.to} className={tabClass}>
                  <TabIcon size={22} aria-hidden="true" />
                  {item.short}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className={styles.chatSlot}>
        <ChatbotWidget />
      </div>
    </div>
  );
}
