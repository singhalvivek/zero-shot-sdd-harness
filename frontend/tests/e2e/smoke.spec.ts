import { test, expect } from '@playwright/test'
import path from 'node:path'

// Resolve relative to the Playwright config root (frontend/) to stay CJS-safe.
const SAMPLE_CSV = path.join(process.cwd(), 'tests', 'e2e', 'fixtures', 'sample.csv')

// Primary Phase-1 journey against the live backend serving the static export at :8001/app/.
test('upload CSV -> ask -> streamed answer; stubs are labelled', async ({ page }) => {
  // Navigate to the baseURL itself (http://localhost:8001/app/). Using an
  // absolute '/' would drop the /app/ path prefix and hit the API root (404).
  await page.goto('./')

  // 1. Page loads and is styled.
  await expect(page.getByRole('heading', { name: 'Personal Data Analysis Agent' })).toBeVisible()
  await expect(page.getByTestId('upload-panel')).toBeVisible()

  // Stubs are visibly labelled "coming soon" so they're never mistaken for bugs.
  const comingSoon = page.getByText(/coming soon/i)
  await expect(comingSoon.first()).toBeVisible()
  expect(await comingSoon.count()).toBeGreaterThan(2)
  await expect(page.getByTestId('audit-tab-stub')).toBeDisabled()
  await expect(page.getByTestId('multi-file-stub')).toBeVisible()

  // Ask is disabled before a dataset is uploaded.
  await expect(page.getByTestId('ask-button')).toBeDisabled()

  // 2. Upload a CSV (REAL: POST /datasets).
  await page.getByTestId('file-input').setInputFiles(SAMPLE_CSV)
  const summary = page.getByTestId('dataset-summary')
  await expect(summary).toBeVisible({ timeout: 20_000 })
  await expect(summary).toContainText(/rows/i)
  await expect(summary).toContainText('dept')

  // 3. Ask a question (REAL: SSE stream).
  await page.getByTestId('question-input').fill('what is the average salary by department?')
  const askBtn = page.getByTestId('ask-button')
  await expect(askBtn).toBeEnabled()
  await askBtn.click()

  // The question turn renders.
  await expect(page.getByTestId('conversation-turn').first()).toBeVisible()

  // 4. A streamed answer with real text appears.
  const answer = page.getByTestId('answer-text').first()
  await expect(answer).toBeVisible({ timeout: 45_000 })
  await expect(answer).not.toBeEmpty()

  // The token-usage display remains a labelled stub even in P1.
  await expect(page.getByTestId('token-usage-stub').first()).toBeVisible()
})
