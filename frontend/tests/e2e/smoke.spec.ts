import { test, expect } from '@playwright/test'
import path from 'node:path'

// Resolve relative to the Playwright config root (frontend/) to stay CJS-safe.
const SAMPLE_CSV = path.join(process.cwd(), 'tests', 'e2e', 'fixtures', 'sample.csv')

// Primary journey against the live backend serving the static export at :8001/app/.
// Phase 1 path STILL works, and Phase-2 features (token badge, follow-up chips, audit) are now real.
test('upload -> ask -> streamed answer with real token badge + chips; no stubs remain', async ({
  page,
}) => {
  // Navigate to the baseURL itself (http://localhost:8001/app/). Using an
  // absolute '/' would drop the /app/ path prefix and hit the API root (404).
  await page.goto('./')

  // 1. Page loads and is styled.
  await expect(page.getByRole('heading', { name: 'Personal Data Analysis Agent' })).toBeVisible()
  await expect(page.getByTestId('upload-panel')).toBeVisible()

  // Phase 3 is the FINAL phase: NOTHING is stubbed any more.
  expect(await page.getByText(/coming soon/i).count()).toBe(0)
  await expect(page.getByTestId('session-switcher-toggle')).toBeVisible()

  // The audit tab is now a REAL, enabled tab (no longer a disabled stub).
  await expect(page.getByTestId('audit-tab')).toBeEnabled()

  // Ask is disabled before a dataset is uploaded.
  await expect(page.getByTestId('ask-button')).toBeDisabled()

  // 2. Upload a CSV (REAL: POST /datasets).
  await page.getByTestId('file-input').setInputFiles(SAMPLE_CSV)
  const summary = page.getByTestId('dataset-item').first()
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
  // Wait for the SECOND turn to finish completing (its token badge only renders on
  // the `done` event, after which the backend has finalized that run's AuditLog
  // row). Otherwise the newest audit row can still be the in-flight running row.
  await expect(page.getByTestId('token-usage-badge').nth(1)).toBeVisible({ timeout: 30_000 })

  // 7. The Audit tab shows the prior queries (newest first).
  await page.getByTestId('audit-tab').click()
  await expect(page.getByTestId('audit-panel')).toBeVisible()
  const rows = page.getByTestId('audit-row')
  await expect(rows.first()).toBeVisible({ timeout: 30_000 })
  // At least one finalized row shows real token counts. Use a refresh + a resilient
  // matcher (the very newest row is finalized by now, but assert on the group so a
  // still-settling running row never flakes the check).
  await page.getByTestId('audit-refresh').click()
  await expect(
    page.getByTestId('audit-tokens').filter({ hasText: /prompt \+ \d+ completion tokens/i }).first(),
  ).toBeVisible({ timeout: 30_000 })
})

// Regression (BLOCKER 1): a run that created an AuditLog row with status="running"
// and NULL token counts (agent error / abandoned stream / crash before the
// completing persist) must NOT white-screen the whole app when the Audit tab
// renders it. Previously `entry.prompt_tokens.toLocaleString()` threw a TypeError
// on the null field and unmounted the entire React tree.
test('audit tab renders NULL-token running rows without white-screening', async ({ page }) => {
  await page.goto('./')

  // Fail the test immediately if any uncaught client exception fires (the
  // symptom of the crash we are guarding against).
  const pageErrors: string[] = []
  page.on('pageerror', err => pageErrors.push(String(err)))

  // Seed a session + dataset, then start (and abandon) an ask so the backend
  // creates a status="running", NULL-token AuditLog row via _prepare — exactly
  // the row shape that used to crash the panel.
  await page.getByTestId('file-input').setInputFiles(SAMPLE_CSV)
  await expect(page.getByTestId('dataset-item').first()).toBeVisible({ timeout: 20_000 })

  const sessionId = await page.evaluate(async () => {
    // Upload creates the session; read it back off the running audit list once we
    // fire an ask. Trigger an ask via fetch and immediately abort so the run
    // never reaches the completing persist -> leaves a running/NULL-token row.
    const up = await fetch('/sessions')
    const body = await up.json()
    const sid: string = body.data[0].session_id
    const controller = new AbortController()
    const p = fetch(`/sessions/${sid}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ question: 'seed a running audit row then abandon' }),
      signal: controller.signal,
    }).catch(() => {})
    // Give the server a moment to run _prepare (writes the running row) then abort.
    await new Promise(r => setTimeout(r, 800))
    controller.abort()
    await p
    return sid
  })
  expect(sessionId).toBeTruthy()

  // Open the Audit tab: the panel must render (not white-screen) and show a row
  // whose token cell degrades gracefully rather than throwing.
  await page.getByTestId('audit-tab').click()
  await expect(page.getByTestId('audit-panel')).toBeVisible()
  await page.getByTestId('audit-refresh').click()
  await expect(page.getByTestId('audit-row').first()).toBeVisible({ timeout: 30_000 })

  // The app is still alive and interactive — the "Application error" white-screen
  // would have removed the heading and the tab controls.
  await expect(page.getByRole('heading', { name: 'Personal Data Analysis Agent' })).toBeVisible()
  await expect(page.getByTestId('chat-tab')).toBeVisible()

  expect(pageErrors, `uncaught client exceptions: ${pageErrors.join('; ')}`).toHaveLength(0)
})
