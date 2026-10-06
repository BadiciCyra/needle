import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Geliştirmede /api istekleri FastAPI'ye gider (Docker'daki nginx de aynı yolu kullanır)
const API_URL = process.env.NEEDLE_API_URL ?? 'http://127.0.0.1:8010'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: API_URL, changeOrigin: true, rewrite: (path) => path.replace(/^\/api/, '') },
      '/openapi.json': { target: API_URL, changeOrigin: true }, // /api/docs sayfası şemayı kökten ister
    },
  },
})
