// Dọn DOM giữa các test (Vitest không bật globals nên Testing Library không tự đăng ký cleanup).
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
});
