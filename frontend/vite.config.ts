import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        // 在 Docker 容器内使用服务名 backend（同一 Docker 网络内可通过服务名访问）
        // 注意：Vite 配置在服务器启动时读取，process.env 可能无法正确读取
        // 如果需要在本地开发，可以修改为 'http://localhost:8000'
        target: 'http://backend:8000',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path, // 保持路径不变
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('Sending Request to the Target:', req.method, req.url);
          });
          proxy.on('proxyRes', (proxyRes, req, _res) => {
            console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
          });
        },
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})