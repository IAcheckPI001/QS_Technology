// Cấu hình Workspace đọc từ biến môi trường Vite (FRONTEND_REQUIREMENTS.md mục 18.2).

// Gốc URL của dịch vụ AI. Để trống: gọi cùng origin (dev qua Vite proxy, production qua reverse
// proxy cùng domain) để cookie phiên HttpOnly của Workspace được gửi kèm.
export const API_BASE = (import.meta.env.VITE_WORKSPACE_API_URL || '').replace(/\/$/, '');

// Dữ liệu giả, chỉ khi chạy dev, mặc định tắt (TR-16). VITE_WORKSPACE_FIXTURES:
// - "1": mọi vùng chưa có hoặc chưa chạy được API (auth, conversations…);
// - danh sách vùng cách nhau dấu phẩy, vd "auth": đăng nhập giả nhưng hội thoại gọi API thật
//   (dùng khi backend :8000 chạy mà chưa có B1).
const FIXTURE_SETTING = import.meta.env.DEV ? String(import.meta.env.VITE_WORKSPACE_FIXTURES || '').trim() : '';
const FIXTURE_AREAS = new Set(FIXTURE_SETTING.split(',').map((area) => area.trim()).filter(Boolean));

export function fixturesFor(area) {
  return FIXTURE_SETTING === '1' || FIXTURE_AREAS.has(area);
}

/** Có ít nhất một vùng chạy dữ liệu giả (để hiện ghi chú "dữ liệu giả" cho người thử). */
export const USE_FIXTURES = FIXTURE_AREAS.size > 0;

// Tên cookie chứa CSRF token do backend đặt khi đăng nhập (mục 14.2). Giả định chờ B1 chốt.
export const CSRF_COOKIE = 'ws_csrf';
export const CSRF_HEADER = 'X-CSRF-Token';
