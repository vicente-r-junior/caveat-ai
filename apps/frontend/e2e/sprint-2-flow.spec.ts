import { expect, test } from '@playwright/test';

// Sprint 2 — full user flow E2E.
//
// All backend API calls are intercepted via page.route() so the test does
// NOT depend on a running FastAPI process or a live Ollama. The Vite dev
// server (5173) still boots from playwright.config.ts so the React app
// loads. This is the same pattern Sprint 1 used for the backend slice but
// inverted — here the UI is real and the backend is mocked.

test.describe('Sprint 2 — full upload → processing → review flow', () => {
  test.beforeEach(async ({ page }) => {
    // Always present.
    await page.route('**/api/health', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'ok', model: 'gemma4:e4b' }),
      }),
    );
    await page.route('**/api/documents/', async (route) => {
      const req = route.request();
      if (req.method() === 'POST') {
        return route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            document_id: 'doc-123',
            filename: 'test.pdf',
            page_count: 8,
            contract_type: null,
          }),
        });
      }
      // GET — recent reviews start empty.
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });
  });

  test('happy path: upload → processing → findings → accept + dismiss + disclaimer', async ({
    page,
  }) => {
    // Mock analyze with a small delay so the processing screen is observable.
    await page.route('**/api/analyze/doc-123', async (route) => {
      await new Promise((r) => setTimeout(r, 800));
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          document_id: 'doc-123',
          contract_type: 'MSA',
          findings: [
            {
              severity: 'high',
              title: 'Liability cap dangerously low',
              quote:
                "In no event shall either party's aggregate liability exceed three (3) months of fees.",
              explanation: 'A 3-month cap is well below market.',
              redline:
                'Replace three (3) months with twelve (12) months.',
            },
            {
              severity: 'medium',
              title: 'Termination forfeits prepayments',
              quote:
                'Customer is not entitled to any refund of prepaid amounts upon termination.',
              explanation: 'Industry norm is pro-rata refund.',
              redline: '',
            },
          ],
          client_summary: {
            what_this_contract_is: 'An MSA.',
            what_youre_committing_to: 'Services.',
            biggest_risks: ['Low cap.'],
            recommendation: 'Negotiate.',
            disclaimer:
              'AI-generated output — attorney review required.',
          },
          warnings: [],
          elapsed_seconds: 1.2,
        }),
      });
    });

    // 1. Land on Upload.
    await page.goto('/');
    await expect(page.getByText(/Read the contract\./i)).toBeVisible();

    // 2. Pick the file via the hidden input.
    await page.locator('input[type="file"]').setInputFiles({
      name: 'test.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 fake'),
    });

    // 3. Processing screen.
    await expect(page).toHaveURL(/\/processing\/doc-123$/);
    await expect(page.getByText(/Reading/)).toBeVisible();
    await expect(page.getByText(/carefully\./)).toBeVisible();

    // 4. Cold-start sub-line is honest about timing.
    await expect(
      page.getByText(/First analysis after starting may take 3–5 min/),
    ).toBeVisible();

    // 5. Review screen — wait for tab bar.
    await expect(page).toHaveURL(/\/review\/doc-123$/, { timeout: 10_000 });
    await expect(page.getByTestId('tab-findings')).toBeVisible();

    // 6. Findings is the active tab.
    await expect(page.getByTestId('tab-findings')).toHaveAttribute(
      'aria-current',
      'page',
    );
    const cards = page.getByTestId('finding-card');
    await expect(cards).toHaveCount(2);

    // 7. Burgundy citation block per finding (Constitution II).
    const quotes = page.getByTestId('finding-quote');
    await expect(quotes).toHaveCount(2);
    await expect(quotes.first()).toContainText(
      "In no event shall either party's aggregate liability",
    );

    // 8. Accept on the first finding flips its visual + data-state.
    const firstAccept = page
      .getByTestId('finding-card')
      .nth(0)
      .getByTestId('finding-accept');
    await firstAccept.click();
    await expect(firstAccept).toHaveText(/✓ Accepted/);
    await expect(page.getByTestId('finding-card').nth(0)).toHaveAttribute(
      'data-state',
      'accepted',
    );

    // 9. Dismiss the second finding hides it.
    const secondDismiss = page
      .getByTestId('finding-card')
      .nth(1)
      .getByTestId('finding-dismiss');
    await secondDismiss.click();
    await expect(page.getByTestId('finding-card')).toHaveCount(1);

    // 10. Disclaimer footer visible at the bottom (Constitution IV).
    await expect(page.getByTestId('disclaimer-footer')).toBeVisible();
    await expect(
      page.getByText(/AI-generated output.*attorney review required/i),
    ).toBeVisible();
  });

  test('honest empty state: findings=[] + warnings → banner + "Analysis incomplete", NEVER "no risks" / "safe"', async ({
    page,
  }) => {
    const warnings = [
      'Analyze stage on first pass: model output had no usable `findings` field.',
      'Client summary: model omitted or left empty: what_this_contract_is, recommendation.',
    ];

    // Override documents/ POST to return a different doc id for clarity.
    await page.route('**/api/documents/', async (route) => {
      const req = route.request();
      if (req.method() === 'POST') {
        return route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            document_id: 'doc-456',
            filename: 'sparse.pdf',
            page_count: 12,
            contract_type: null,
          }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    await page.route('**/api/analyze/doc-456', async (route) => {
      await new Promise((r) => setTimeout(r, 400));
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          document_id: 'doc-456',
          contract_type: 'MSA',
          findings: [],
          client_summary: {
            what_this_contract_is: '',
            what_youre_committing_to: '',
            biggest_risks: [],
            recommendation: '',
            disclaimer:
              'AI-generated output — attorney review required.',
          },
          warnings,
          elapsed_seconds: 360.3,
        }),
      });
    });

    // Drive the flow.
    await page.goto('/');
    await page.locator('input[type="file"]').setInputFiles({
      name: 'sparse.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 fake-sparse'),
    });

    await expect(page).toHaveURL(/\/processing\/doc-456$/);
    await expect(page).toHaveURL(/\/review\/doc-456$/, { timeout: 10_000 });

    // Warnings banner shows up + verbatim warning text.
    await expect(page.getByTestId('warnings-banner')).toBeVisible();
    for (const w of warnings) {
      await expect(page.getByText(w)).toBeVisible();
    }

    // Honest empty-state copy is present.
    await expect(page.getByText(/Analysis incomplete/i)).toBeVisible();
    await expect(
      page.getByTestId('findings-empty-with-warnings'),
    ).toBeVisible();

    // Constitution VI negatives — neither false-reassurance phrase appears.
    await expect(page.getByText(/no risks/i)).toHaveCount(0);
    await expect(page.getByText(/\bsafe\b/i)).toHaveCount(0);

    // Disclaimer is still present.
    await expect(page.getByTestId('disclaimer-footer')).toBeVisible();
  });
});
