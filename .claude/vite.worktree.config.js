// Preview cho worktree: chạy song song với dev server 5173 của checkout chính.
// Backend (localhost:8000) chỉ cho CORS origin 5173, nên các GET của Support Workspace
// được proxy qua cùng origin 5174 thay vì gọi thẳng 8000. `/api` (widget-backend :8787)
// kế thừa từ vite.config.js.
import process from 'node:process'
import { defineConfig, mergeConfig } from 'vite'
import baseConfig from '../vite.config.js'

const PORT = 5174
const BACKEND = 'http://localhost:8000'
const BACKEND_PATHS = ['/chatbot', '/workspace', '/support-chat', '/ai', '/health', '/intro-stream']

export default mergeConfig(baseConfig, defineConfig({
  define: {
    'import.meta.env.VITE_API_URL': JSON.stringify(`http://localhost:${PORT}`),
    // Preview worktree chạy Workspace với dữ liệu giả cho phần backend chưa có (B1, B6, B7).
    // Mặc định "1" (mọi vùng); backend :8000 đang chạy thì đặt VITE_WORKSPACE_FIXTURES=auth để hội
    // thoại đọc dữ liệu thật.
    'import.meta.env.VITE_WORKSPACE_FIXTURES': JSON.stringify(process.env.VITE_WORKSPACE_FIXTURES ?? '1'),
  },
  server: {
    host: 'localhost',
    port: PORT,
    strictPort: true,
    proxy: Object.fromEntries(BACKEND_PATHS.map((path) => [path, { target: BACKEND, changeOrigin: true }])),
  },
}))
