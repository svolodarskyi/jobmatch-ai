import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // @ts-expect-error – plugin-react v6 targets Vite 8; vitest 3 ships Vite 7 internally.
  // The plugin works correctly at runtime; this suppresses the type-only conflict.
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/setupTests.ts',
  },
})
