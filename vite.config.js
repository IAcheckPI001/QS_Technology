import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    watch: {
      // Thư mục Python/backend và tài liệu không phải mã frontend: không theo dõi
      // (venv có hàng chục nghìn file làm dev server khởi động và tải rất chậm).
      ignored: ['**/.venv-ingest/**', '**/backend/**', '**/widget-backend/**', '**/docs/**'],
    },
    // Widget chat gọi widget-backend cùng origin để cookie HttpOnly hoạt động.
    proxy: {
      '/api': 'http://localhost:8787',
    },
  },
})
