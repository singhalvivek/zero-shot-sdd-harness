import { test, expect } from '@playwright/test'
import path from 'node:path'

const FIXTURES = path.join(process.cwd(), 'tests', 'e2e', 'fixtures')
const SAMPLE_CSV = path.join(FIXTURES, 'sample.csv')
const DEPARTMENTS_CSV = path.join(FIXTURES, 'departments.csv')

// Phase 3 (FINAL): multi-file upload, Excel acceptance in the picker, the persistent
// session switcher, and the absence of every "coming soon" stub. Runs against the live
// backend serving the static export at :8001/app/.
test('multi-file upload + cross-file question + persistent session switcher; no stubs remain', async ({
  page,
}) => {
  await page.goto('./')

  await expect(page.getByRole('heading', { name: 'Personal Data Analysis Agent' })).toBeVisible()

  // (d) NOTHING is stubbed — no "coming soon" text anywhere on the page.
  expect(await page.getByText(/coming soon/i).count()).toBe(0)

  // The file picker accepts Excel as well as CSV.
  const accept = await page.getByTestId('file-input').getAttribute('accept')
  expect(accept).toContain('.csv')
  expect(accept).toContain('.xlsx')
  expect(accept).toContain('.xls')

  // (a) Upload a first CSV into a fresh session.
  await page.getByTestId('file-input').setInputFiles(SAMPLE_CSV)
  await expect(page.getByTestId('dataset-item')).toHaveCount(1, { timeout: 20_000 })
  await expect(page.getByTestId('dataset-count')).toContainText('1 loaded')

  // (a) Upload a SECOND file into the SAME session — both appear in the loaded list.
  await page.getByTestId('file-input').setInputFiles(DEPARTMENTS_CSV)
  await expect(page.getByTestId('dataset-item')).toHaveCount(2, { timeout: 20_000 })
  await expect(page.getByTestId('dataset-count')).toContainText('2 loaded')
  await expect(page.getByTestId('multi-file-hint')).toBeVisible()
  // Both source tables are visible by name.
  await expect(page.getByTestId('dataset-list')).toContainText('region')
  await expect(page.getByTestId('dataset-list')).toContainText('salary')

  // (b) Ask a cross-file question and get a real answer (the agent joins the two tables).
  await page
    .getByTestId('question-input')
    .fill('For each region, what is the average salary across the two tables?')
  const askBtn = page.getByTestId('ask-button')
  await expect(askBtn).toBeEnabled()
  await askBtn.click()

  const answer = page.getByTestId('answer-text').first()
  await expect(answer).toBeVisible({ timeout: 180_000 })
  await expect(answer).not.toBeEmpty()

  // (c) The session switcher lists this session.
  await page.getByTestId('session-switcher-toggle').click()
  await expect(page.getByTestId('session-switcher-panel')).toBeVisible()
  const items = page.getByTestId('session-item')
  await expect(items.first()).toBeVisible({ timeout: 20_000 })
  // The active session shows 2 datasets.
  await expect(page.getByTestId('session-dataset-count').first()).toContainText('2')

  // Start a NEW session — the loaded datasets clear.
  await page.getByTestId('new-session').click()
  await expect(page.getByTestId('dataset-item')).toHaveCount(0)
  await expect(page.getByTestId('ask-button')).toBeDisabled()

  // (c) Resume the prior session from the switcher — datasets + history are restored.
  await page.getByTestId('session-switcher-toggle').click()
  await page.getByTestId('session-item').first().click()
  await expect(page.getByTestId('dataset-item')).toHaveCount(2, { timeout: 20_000 })
  // The prior conversation turn is rehydrated.
  await expect(page.getByTestId('conversation-turn').first()).toBeVisible({ timeout: 10_000 })

  // Final guard: still no stubs after all interactions.
  expect(await page.getByText(/coming soon/i).count()).toBe(0)
})
