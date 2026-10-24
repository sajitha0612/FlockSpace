import { defineConfig, searchForWorkspaceRoot } from 'vite'
import vue from '@vitejs/plugin-vue'

// The dev server forwards API and WebSocket traffic to FastAPI, so the browser only ever talks to one origin.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // the offline demo reuses the backend's starter question bank; allow that one file and nothing else outside frontend/
    fs: { allow: [searchForWorkspaceRoot(process.cwd()), '../backend/app/seed/bank.json'] },
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
})
