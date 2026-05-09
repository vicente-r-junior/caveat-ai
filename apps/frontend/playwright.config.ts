import { defineConfig, devices } from '@playwright/test';

// Playwright config for the Caveat AI frontend E2E suite.
//
// Sprint 0 has a single test that proves the wire works: React loads,
// fetches /api/health from the FastAPI backend, and renders the response.
// The webServer block boots both the backend (uvicorn on 127.0.0.1:8787)
// and the frontend (Vite on 5173) so `pnpm test:e2e` works from a clean
// state. Both servers run on localhost only — Constitution I (local-only
// by construction) is preserved end-to-end.
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command:
        'cd ../backend && uv run uvicorn caveat.main:app --host 127.0.0.1 --port 8787',
      port: 8787,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: 'pnpm dev',
      port: 5173,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
