import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({ plugins: [react()], server: { proxy: { '/api': 'http://127.0.0.1:7331', '/health': 'http://127.0.0.1:7331' } },
  build: {rollupOptions:{output:{manualChunks:{three:['three'],graph:['3d-force-graph']}}}} });
