import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/static/chat/flow_builder_dist/',
  build: {
    outDir: path.resolve(__dirname, '../chat/static/chat/flow_builder_dist'),
    emptyOutDir: true,
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/flow_builder_app.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name].[ext]',
      },
    },
  },
  server: {
    port: 5173,
    cors: true,
  },
});
