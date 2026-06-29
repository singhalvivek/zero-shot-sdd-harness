import { defineConfig, devices } from '@playwright/test'

// The Phase 1 smoke E2E targets the live backend serving the static export at :8001/app/.
// Run AFTER the backend slices land: `pnpm exec playwright test tests/e2e/`.
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8001/app/',
    trace: 'on-first-retry',
    actionTimeout: 15_000,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
