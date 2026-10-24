import { resolve } from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { rc1EvidencePlugin } from "./vite/rc1EvidencePlugin";

// cwd es frontend/ en local y /app en Docker. ../evidence es el directorio montado en /evidence.
const frontendRoot = resolve(".");
const evidenceRoot = resolve(frontendRoot, "../evidence");

// La evidence queda fuera de frontend/. En Docker, compose monta ese directorio
// en /evidence, que es ../evidence desde /app. El plugin solo lee. server.fs.allow
// incluye ese directorio por si Vite resuelve un archivo importado fuera de la raíz;
// el módulo virtual no publica los JSON.
export default defineConfig({
  plugins: [react(), rc1EvidencePlugin(evidenceRoot)],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    fs: {
      allow: [frontendRoot, evidenceRoot],
    },
    watch: {
      usePolling: true,
      interval: 300,
    },
  },
});
