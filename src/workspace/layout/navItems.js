// Mục điều hướng chính (Q22, Q27). Ẩn mục theo quyền, không theo vai trò.

import { KeyRound, Layers, MessageSquare, Users } from 'lucide-react';
import { S } from '../strings.vi.js';
import { PERMISSIONS } from '../auth/permissions.js';

export const NAV_ITEMS = [
  { to: '/conversations', icon: MessageSquare, label: S.nav.conversations, short: S.nav.conversationsShort, permission: PERMISSIONS.conversationsRead },
  { to: '/documents', icon: Layers, label: S.nav.documents, short: S.nav.documentsShort, permission: PERMISSIONS.chunksRead },
  { to: '/keys', icon: KeyRound, label: S.nav.keys, short: S.nav.keysShort, permission: PERMISSIONS.serviceKeysManage },
  { to: '/users', icon: Users, label: S.nav.users, short: S.nav.usersShort, permission: PERMISSIONS.usersManage },
];
