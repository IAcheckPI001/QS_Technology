import { useContext } from 'react';
import { AuthContext } from './AuthContext.js';

/** { status: 'loading'|'authenticated'|'anonymous'|'unavailable', user, error, login, logout, reload } */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth phải dùng bên trong AuthProvider');
  return context;
}
