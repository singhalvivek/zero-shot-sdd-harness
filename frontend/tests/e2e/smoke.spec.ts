import { test, expect } from '@playwright/test'
import path from 'node:path'

// Resolve relative to the Playwright config root (frontend/) to stay CJS-safe.
const SAMPLE_CSV = path.join(process.cwd(), 'tests', 'e2e', 'fixtures', 'sample.csv')

// Primary journey against the live backend serving the static export at :8001/app/.
// Phase 1 path STILL works, and Phase-2 features (token badge, follow-up chips, audit) are now real.
test('upload -> ask -> streamed answer with real token badge + chips; Phase-3 stubs stay labelled', async ({
  page,
}) => {
  // Navigate to the baseURL itself (http://localhost:8001/app/). Using an
  // absolute '/' would drop the /app/ path prefix and hit the API root (404).
  await page.goto('./')

  // 1. Page loads and is styled.
  await expect(page.getByRole('heading', { name: 'Personal Data Analysis Agent' })).toBeVisible()
  await expect(page.getByTestId('upload-panel')).toBeVisible()

  // Phase-3 stubs remain visibly labelled "coming soon" so they're never mistaken for bugs.
  const comingSoon = page.getByText(/coming soon/i)
  await expect(comingSoon.first()).toBeVisible()
  expect(await comingSoon.count()).toBeGreaterThanOrEqual(2)
  await expect(page.getByTestId('multi-file-stub')).toBeVisible()

  // The audit tab is now a REAL, enabled tab (no longer a disabled stub).
  await expect(page.getByTestId('audit-tab')).toBeEnabled()

  // Ask is disabled before a dataset is uploaded.
  await expect(page.getByTestId('ask-button')).toBeDisabled()

  // 2. Upload a CSV (REAL: POST /datasets).
  await page.getByTestId('file-input').setInputFiles(SAMPLE_CSV)
  const summary = page.getByTestId('dataset-summary')
  await expect(summary).toBeVisible({ timeout: 20_000 })
  await expect(summary).toContainText(/rows/i)
  await expect(summary).toContainText('dept')

  // 3. Ask a clear question (REAL: SSE stream).
  await page.getByTestId('question-input').fill('what is the average salary by department?')
  const askBtn = page.getByTestId('ask-button')
  await expect(askBtn).toBeEnabled()
  await askBtn.click()

  // The question turn renders.
  await expect(page.getByTestId('conversation-turn').first()).toBeVisible()

  // 4. A streamed answer with real text appears.
  const answer = page.getByTestId('answer-text').first()
  await expect(answer).toBeVisible({ timeout: 90_000 })
  await expect(answer).not.toBeEmpty()

  // 5. The real token-usage badge appears with prompt/completion counts.
  const badge = page.getByTestId('token-usage-badge').first()
  await expect(badge).toBeVisible({ timeout: 15_000 })
  await expect(badge).toContainText(/prompt \+ \d+ completion tokens/i)

  // 6. Follow-up chips are real, clickable buttons.
  const chip = page.getByTestId('followup-chip').first()
  await expect(chip).toBeVisible({ timeout: 15_000 })
  await expect(chip).toBeEnabled()
  const chipText = (await chip.textContent())?.trim() ?? ''
  await chip.click()

  // Clicking a chip submits it as the next question — a new turn appears with that text.
  await expect(page.getByTestId('conversation-turn')).toHaveCount(2, { timeout: 15_000 })
  if (chipText) {
    await expect(page.getByText(chipText).last()).toBeVisible()
  }
  // And the second turn produces its own answer.
  await expect(page.getByTestId('answer-text').nth(1)).toBeVisible({ timeout: 90_000 })

  // 7. The Audit tab shows the prior queries (newest first).
  await page.getByTestId('audit-tab').click()
  await expect(page.getByTestId('audit-panel')).toBeVisible()
  const rows = page.getByTestId('audit-row')
  await expect(rows.first()).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('audit-tokens').first()).toContainText(/prompt \+ \d+ completion tokens/i)
})
