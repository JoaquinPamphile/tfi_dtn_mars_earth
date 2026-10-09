import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Polling para que el hot reload funcione con el volumen de Docker en Windows.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
});
