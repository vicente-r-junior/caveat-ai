import { defineConfig, type UserConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite + Vitest configuration for the Caveat AI frontend.
// The /api proxy keeps the dev server (5173) talking to FastAPI (8787)
// without CORS, and without ever pointing at an external host
// (Constitution I — local-only by construction).
//
// The `test` key is consumed by Vitest at runtime; it is augmented onto
// UserConfig via vitest's type extension. We use a typed intersection
// here so the build (`tsc -b`) doesn't trip on the augmentation when
// Vite and Vitest ship slightly different `Plugin` definitions.
type ViteConfigWithTest = UserConfig & {
  test: {
    environment: 'jsdom';
    globals: boolean;
    setupFiles: string;
    css: boolean;
    exclude: string[];
  };
};

const config: ViteConfigWithTest = {
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8787',
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test-setup.ts',
    css: false,
    // Playwright owns the e2e/ directory; vitest must not collect from it.
    exclude: ['node_modules', 'dist', 'e2e', '**/*.config.*'],
  },
};

export default defineConfig(config);
