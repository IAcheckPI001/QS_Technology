// Cấu hình Workspace đọc từ biến môi trường Vite (FRONTEND_REQUIREMENTS.md mục 18.2).

// Gốc URL của dịch vụ AI. Để trống: gọi cùng origin (dev qua Vite proxy, production qua reverse
// proxy cùng domain) để cookie phiên HttpOnly của Workspace được gửi kèm.
export const API_BASE = (import.meta.env.VITE_WORKSPACE_API_URL || '').replace(/\/$/, '');

// Dữ liệu giả cho các màn chưa có API (B1, B6, B7). Chỉ có hiệu lực khi chạy dev, mặc định tắt
// (TR-16). Hội thoại luôn dùng API thật vì backend đã có.
export const USE_FIXTURES = import.meta.env.DEV && import.meta.env.VITE_WORKSPACE_FIXTURES === '1';

// Tên cookie chứa CSRF token do backend đặt khi đăng nhập (mục 14.2). Giả định chờ B1 chốt.
export const CSRF_COOKIE = 'ws_csrf';
export const CSRF_HEADER = 'X-CSRF-Token';
