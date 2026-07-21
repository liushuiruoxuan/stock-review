import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发模式：前端(5173) 将 /api 代理到本地后端(8000)
// 生产模式：npm run build 后由后端 server.py 直接托管 dist，/api 同源
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500
  }
})
