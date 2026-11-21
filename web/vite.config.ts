import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    // Always 5173: the API's CORS allow-list (docs/contract.md §1) only accepts this port.
    // strictPort makes `npm run dev` fail loudly instead of silently moving to 5174.
    port: 5173,
    strictPort: true,
    // Allow importing ../shared/fixtures/*.json (contract mocks + demo presets).
    fs: { allow: ['..'] },
  },
})
