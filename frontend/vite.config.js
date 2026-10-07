import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Proxy /api ke Django supaya browser melihat satu origin (tanpa CORS).
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
