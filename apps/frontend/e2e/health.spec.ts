import { expect, test } from '@playwright/test';

// Sprint 0 — single end-to-end test proving the browser → React → FastAPI
// wire is connected. Asserts the React app renders, calls /api/health
// (proxied through Vite to the local FastAPI server on 8787), and
// surfaces the backend's status and configured model name to the user.
//
// No Ollama, no pipeline, no real model — Sprint 0 is scaffolding only.
test('frontend renders backend health response', async ({ page }) => {
  await page.goto('/');

  // 1. Heading is rendered immediately by React.
  await expect(
    page.getByRole('heading', { name: 'Caveat AI' }),
  ).toBeVisible();

  // 2. Eyebrow text identifies the sprint.
  await expect(page.getByText('Sprint 0 — Scaffold')).toBeVisible();

  // 3. /api/health resolved successfully and the status line updated.
  const statusLine = page.getByTestId('status-line');
  await expect(statusLine).toBeVisible();
  await expect(statusLine).toHaveText('Backend status: ok');

  // 4. Status pill reflects the model returned by the backend.
  const statusPill = page.getByTestId('status-pill');
  await expect(statusPill).toBeVisible();
  await expect(statusPill).toContainText('gemma4:e4b');
  await expect(statusPill).toContainText('Local');
  await expect(statusPill).toContainText('Gemma 4');

  // 5. Disclaimer footer is part of the product (Constitution IV).
  // The text is rendered lowercase and visually transformed by Tailwind's
  // `uppercase` utility, so we match case-insensitively via regex.
  await expect(
    page.getByText(/AI-generated output\s*—\s*attorney review required/i),
  ).toBeVisible();
});
