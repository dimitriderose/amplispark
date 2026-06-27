import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/react-icons'))   return 'vendor-icons'
          if (id.includes('node_modules/firebase'))      return 'vendor-firebase'
          if (id.includes('node_modules/react-router-dom') ||
              id.includes('node_modules/react-router/') ||
              id.includes('node_modules/@remix-run'))    return 'vendor-router'
          if (id.includes('node_modules/react/') ||
              id.includes('node_modules/react-dom/'))    return 'vendor-react'
        },
      },
    },
  },
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8080', changeOrigin: true, ws: true, proxyTimeout: 180000, timeout: 180000 },
      '/health': 'http://localhost:8080',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: ['src/test/**', '**/*.d.ts', 'dist/**', 'src/api/firebase.ts'],
      thresholds: { lines: 90, functions: 90, branches: 90, statements: 90 },
    },
  },
})
