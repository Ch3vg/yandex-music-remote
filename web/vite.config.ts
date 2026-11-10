import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Телефон открывает пульт на порту Python-сервера (8001), не на порту Vite.
// Сборка кладётся в web/dist, её потом отдаёт тот же сервер.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/ws': { target: 'ws://127.0.0.1:8001', ws: true },
      '/api': 'http://127.0.0.1:8001',
      '/search': 'http://127.0.0.1:8001',
      '/network-info': 'http://127.0.0.1:8001',
      '/qr': 'http://127.0.0.1:8001',
      '/sw.js': 'http://127.0.0.1:8001',
      '/manifest.webmanifest': 'http://127.0.0.1:8001',
      '/apple-touch-icon.png': 'http://127.0.0.1:8001',
      '/icon-192.png': 'http://127.0.0.1:8001',
      '/icon-512.png': 'http://127.0.0.1:8001',
    },
  },
});
