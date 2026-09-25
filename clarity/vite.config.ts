import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Same-origin browser requests go only to the local synthetic API.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8788' },
  },
  preview: {
    host: '127.0.0.1',
    port: 4173,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8788' },
  },
});
