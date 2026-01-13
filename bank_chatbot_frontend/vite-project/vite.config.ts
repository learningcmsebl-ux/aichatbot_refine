import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Listen on all network interfaces
    port: 3000,
    strictPort: false, // Try next available port if 3000 is taken
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        // Important: Don't buffer streaming responses
        buffer: false,
        // Forward headers that might contain client IP
        headers: {
          // Vite will forward X-Client-IP if sent by frontend
        },
      }
    }
  }
})
