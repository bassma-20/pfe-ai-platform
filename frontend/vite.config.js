import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        timeout: 480000,        // 8 minutes (boucle réparation progressive = jusqu'à 6 appels LLM)
        proxyTimeout: 480000,   // timeout coté proxy aussi
      }
    }
  }
})