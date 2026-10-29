import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Widget chat gọi widget-backend cùng origin để cookie HttpOnly hoạt động.
    proxy: {
      '/api': 'http://localhost:8787',
    },
  },
})
