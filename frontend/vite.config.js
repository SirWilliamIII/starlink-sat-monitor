import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    host: true,
    allowedHosts: [
      "will.ngrok.dev",
      ".ngrok.dev",
      "localhost",
      "mbp.mastodon-snake.ts.net",
      ".mastodon-snake.ts.net",
    ],
    proxy: {
      // Proxy API requests to your backend
      "/api": {
        target: "http://localhost:5050",
        changeOrigin: true,
        // Optional: rewrite the path
        // rewrite: (path) => path.replace(/^\/api/, '')
      },
    },
  },
});
