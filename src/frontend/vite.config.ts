import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The frontend talks to the backend through a dev proxy, so components use relative '/api' paths and
// no CORS configuration is needed in development.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Bind every interface, not just the IPv6 loopback Vite defaults to in this environment: with the
    // default, http://127.0.0.1:5173 refuses the connection (and so does every IPv4-resolving tool or
    // browser), while only http://localhost:5173 works. It also lets a second device open the demo.
    host: true,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET ?? 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
