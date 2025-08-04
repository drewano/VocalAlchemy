import path from "path" // <-- Ajoutez cette ligne
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  // V-- Ajoutez toute cette section --V
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // ^-- Fin de la section à ajouter --^
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})