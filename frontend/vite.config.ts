import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/** Dev and the built preview both talk to the local API. The backend has no CORS, so the browser only reaches it through this same-origin proxy. */
const proxy = { '/api': 'http://127.0.0.1:8000', '/health': 'http://127.0.0.1:8000' }

export default defineConfig({
  plugins: [vue()],
  server: { host: '127.0.0.1', proxy },
  preview: { host: '127.0.0.1', proxy },
})
