import react from "@vitejs/plugin-react";

export default {
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: false,
        secure: false,
      }
    }
  }
};
