/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // MapLibre loads its web worker from a file next to its own module. Pre-bundling moves
  // the module into .vite/deps and the worker can't be found, so serve it as is.
  optimizeDeps: { exclude: ['maplibre-gl'] },
  server: {
    // The API runs on :8000 (`uv run uvicorn navigator_api.main:app --reload`).
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: {
    include: ['src/**/*.test.ts'],
  },
})
