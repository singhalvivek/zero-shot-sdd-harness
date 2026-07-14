import { test, expect } from '@playwright/test'

// Primary-journey smoke test against the LIVE app (real Gemini + real CadQuery).
//
// Prerequisites (started by the orchestrator / QA, NOT by this test):
//   cd frontend && pnpm build
//   uv run alembic upgrade head
//   uv run python -m src            # http://localhost:8001/app/
//   cd frontend && npx playwright test
//
// Keeps to ONE real generation to respect the Gemini free-tier quota, and uses
// the cheapest/fastest model.
test('generate a part end-to-end: viewer renders, code + tokens appear', async ({ page }) => {
  await page.goto('/app/')

  // Page loads and is styled (header present).
  await expect(page.getByRole('heading', { name: 'AI CAD Studio' })).toBeVisible()

  // Enter a real prompt.
  await page
    .locator('#prompt')
    .fill('a 40x40x10mm plate with a 6mm center hole')

  // Pick the cheapest model (free-tier friendly).
  await page.locator('#model').selectOption('gemini-3.1-flash-lite')

  // Kick off the real generation.
  await page.getByRole('button', { name: 'Generate', exact: true }).click()

  // Real Gemini + CAD export can take a while — wait generously for the cost
  // panel (only rendered on a completed run).
  const costPanel = page.getByTestId('cost-panel')
  await expect(costPanel).toBeVisible({ timeout: 130_000 })

  // The 3D viewer shows real geometry: a canvas is present and visible.
  const canvas = page.locator('canvas')
  await expect(canvas.first()).toBeVisible()

  // The code panel contains the generated CadQuery (assigns `result`).
  await expect(page.getByText(/result/).first()).toBeVisible()

  // Token/cost panel shows a non-zero token count.
  const tokensText = await page.getByTestId('total-tokens').innerText()
  const tokens = parseInt(tokensText.replace(/[^0-9]/g, ''), 10)
  expect(tokens).toBeGreaterThan(0)
})
