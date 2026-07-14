import { defineConfig, devices } from '@playwright/test'

// E2E runs against the LIVE, single-origin app.
//
// Run order (from repo root):
//   1. cd frontend && pnpm build        # produces frontend/out/
//   2. uv run alembic upgrade head       # migrate the DB
//   3. uv run python -m src              # serve at http://localhost:8001/app/
//   4. cd frontend && npx playwright test
//
// The server (backend + built frontend) is assumed already running when the
// test executes — the orchestrator / QA starts it. We do NOT spawn a webServer
// here because the app is served by FastAPI, not `next start`.
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: 'list',
  timeout: 180_000,
  expect: { timeout: 130_000 },
  use: {
    baseURL: 'http://localhost:8001/app/',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
