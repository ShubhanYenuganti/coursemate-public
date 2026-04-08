import react from "@vitejs/plugin-react";

export default {
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:3001',
        changeOrigin: false,
        secure: false,
      }
    }
  }
};
