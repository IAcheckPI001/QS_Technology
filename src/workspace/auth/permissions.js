// Quyền Workspace (FRONTEND_REQUIREMENTS.md 14.1). Giao diện kiểm quyền, không kiểm tên vai trò,
// để thêm vai trò mới không phải sửa màn hình.

export const PERMISSIONS = {
  conversationsRead: 'conversations:read',
  chunksRead: 'chunks:read',
  chunksReview: 'chunks:review',
  versionsActivate: 'versions:activate',
  serviceKeysManage: 'service_keys:manage',
  usersManage: 'users:manage',
};

export function can(user, permission) {
  if (!permission) return true;
  return Boolean(user && Array.isArray(user.permissions) && user.permissions.includes(permission));
}

export function initials(name = '') {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return '?';
  const first = words[0][0] || '';
  const last = words.length > 1 ? words[words.length - 1][0] : words[0][1] || '';
  return (first + last).toUpperCase();
}
