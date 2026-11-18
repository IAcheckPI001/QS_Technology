import { useContext } from 'react';
import { ToastContext } from './ToastContext.js';

/** show({ message, tone: 'info'|'success'|'error', undo, action: { label, onClick }, duration }) → id */
export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error('useToast phải dùng bên trong ToastProvider');
  return context;
}
