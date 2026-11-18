import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const AI_SERVICE = 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      // Thư mục Python/backend và tài liệu không phải mã frontend: không theo dõi
      // (venv có hàng chục nghìn file làm dev server khởi động và tải rất chậm).
      ignored: ['**/.venv-ingest/**', '**/data/**', '**/.claude/**', '**/backend/**', '**/widget-backend/**', '**/docs/**'],
    },
    proxy: {
      // Widget chat gọi widget-backend cùng origin để cookie HttpOnly hoạt động.
      '/api': 'http://localhost:8787',
      // QS AI Workspace gọi dịch vụ AI cùng origin để cookie phiên Workspace được gửi kèm
      // (FRONTEND_REQUIREMENTS.md 14.2, 18.2). Production dùng reverse proxy cùng domain.
      '/workspace': { target: AI_SERVICE, changeOrigin: true },
      '/chatbot': { target: AI_SERVICE, changeOrigin: true },
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{js,jsx}'],
    setupFiles: ['src/workspace/test/setup.js'],
    restoreMocks: true,
  },
})
