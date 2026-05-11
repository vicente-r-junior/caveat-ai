import { expect, test } from '@playwright/test';

// Sprint 3 — three-tab walkthrough E2E.
//
// Mirrors sprint-2-flow.spec.ts: all backend API calls are intercepted via
// page.route() so the test does NOT depend on a running FastAPI process or
// a live Ollama. The Vite dev server still boots from playwright.config.ts.
//
// The mocked /api/analyze response carries 2 findings + 3 source_sections
// + offsets that land each finding in a distinct section, so the Source tab
// renders both highlights and the cross-tab jump can be verified.

const ANALYZE_BODY = {
  document_id: 'doc-789',
  contract_type: 'Acme Master Services Agreement',
  findings: [
    {
      severity: 'high',
      title: 'Liability cap dangerously low',
      quote: 'liability shall not exceed three months of fees',
      explanation: 'A 3-month cap is well below market.',
      redline: 'Replace three (3) months with twelve (12) months.',
      // Section 0 body starts at char 0; quote sits at 10–58.
      source_offset: { section_index: 0, start: 10, end: 58 },
    },
    {
      severity: 'medium',
      title: 'Termination forfeits prepayments',
      quote: 'all prepaid amounts shall be non-refundable',
      explanation: 'Industry norm is pro-rata refund.',
      redline: '',
      // Section 2 body starts at char 200; quote sits at 210–253.
      source_offset: { section_index: 2, start: 210, end: 253 },
    },
  ],
  client_summary: {
    what_this_contract_is:
      'A Master Services Agreement that governs your ongoing relationship with Acme.',
    what_youre_committing_to:
      'Pay Acme on time, in advance, for all services.',
    biggest_risks: [
      'Liability cap is unusually low.',
      'Termination forfeits prepayments.',
      'No data privacy protections.',
    ],
    recommendation:
      'Do not sign as-is. Negotiate the three items above before executing.',
    disclaimer:
      'This summary is generated locally by Caveat AI. It is a tool to support — not replace — independent review by your attorney.',
  },
  warnings: [],
  elapsed_seconds: 1.4,
  source_sections: [
    {
      idx: 0,
      number: '4.2',
      title: 'Limitation of Liability',
      body: 'In sum,   liability shall not exceed three months of fees regardless of the form of action.',
      char_start: 0,
      char_end: 91,
      page: 1,
    },
    {
      idx: 1,
      number: '5.1',
      title: 'Indemnification',
      body: 'Customer shall defend and indemnify Provider against any third-party claims.',
      char_start: 100,
      char_end: 176,
      page: 2,
    },
    {
      idx: 2,
      number: '7.3',
      title: 'Termination',
      body: 'Upon any termination, all prepaid amounts shall be non-refundable for any reason or no reason.',
      char_start: 200,
      char_end: 294,
      page: 3,
    },
  ],
};

test.describe('Sprint 3 — three-tab walkthrough', () => {
  test.beforeEach(async ({ page }) => {
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
            document_id: 'doc-789',
            filename: 'acme-msa.pdf',
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
    await page.route('**/api/analyze/doc-789', async (route) => {
      await new Promise((r) => setTimeout(r, 400));
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(ANALYZE_BODY),
      });
    });
  });

  test('happy path: upload → processing → findings → summary → source → cross-tab jump back to findings', async ({
    page,
  }) => {
    // 1. Land on Upload.
    await page.goto('/');
    await expect(page.getByText(/Read the contract\./i)).toBeVisible();

    // 2. Drop a synthetic PDF.
    await page.locator('input[type="file"]').setInputFiles({
      name: 'acme-msa.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 fake'),
    });

    // 3. Processing screen.
    await expect(page).toHaveURL(/\/processing\/doc-789$/);
    await expect(page.getByText(/Reading/)).toBeVisible();
    await expect(page.getByText(/carefully\./)).toBeVisible();

    // 4. Disclaimer footer present at every checkpoint.
    await expect(page.getByTestId('disclaimer-footer')).toBeVisible();

    // 5. Review screen — Findings tab active by default with 2 cards.
    await expect(page).toHaveURL(/\/review\/doc-789$/, { timeout: 10_000 });
    await expect(page.getByTestId('tab-findings')).toBeVisible();
    await expect(page.getByTestId('finding-card')).toHaveCount(2);
    await expect(page.getByTestId('disclaimer-footer')).toBeVisible();

    // 6. Click Client summary → four section headings + verbatim disclaimer.
    await page.getByTestId('tab-summary').click();
    await expect(page.getByText('What this contract is')).toBeVisible();
    await expect(page.getByText("What you're committing to")).toBeVisible();
    await expect(page.getByText('The biggest risks')).toBeVisible();
    // The "Recommendation" word also appears as a verdict-box eyebrow; using
    // a heading-specific locator to be unambiguous.
    await expect(
      page.getByRole('heading', { name: /^Recommendation$/, level: 3 }),
    ).toBeVisible();
    const summaryDisclaimer = page.getByTestId('summary-disclaimer');
    await expect(summaryDisclaimer).toBeVisible();
    await expect(summaryDisclaimer).toHaveText(
      ANALYZE_BODY.client_summary.disclaimer,
    );
    await expect(page.getByTestId('disclaimer-footer')).toBeVisible();

    // 7. Click Source → 3 section blocks visible.
    await page.getByTestId('tab-source').click();
    await expect(page.getByTestId('source-section')).toHaveCount(3);
    // Each section heading appears twice (once in the eyebrow, once in the
    // <h3>). Use .first() so Playwright's strict mode is satisfied.
    await expect(
      page.getByText(/Limitation of Liability/i).first(),
    ).toBeVisible();
    await expect(page.getByText(/Indemnification/i).first()).toBeVisible();
    await expect(page.getByText(/Termination/i).first()).toBeVisible();

    // 8. Each finding rendered at least one highlight.
    const highlights = page.getByTestId('source-highlight');
    await expect(highlights).toHaveCount(2);
    await expect(page.getByTestId('disclaimer-footer')).toBeVisible();

    // 9. Click the first highlight → activeTab flips to Findings AND the
    // matching finding card has data-finding-target="true" (briefly).
    await highlights.first().click();
    await expect(page.getByTestId('findings-wrap')).toBeVisible();
    // The first finding card carries data-finding-target="true".
    await expect(
      page.getByTestId('finding-card').first(),
    ).toHaveAttribute('data-finding-target', 'true');

    // 10. Disclaimer footer still visible.
    await expect(page.getByTestId('disclaimer-footer')).toBeVisible();
  });

  test('summary disclaimer is non-removable: tampering with the DOM is reconciled away on re-render', async ({
    page,
  }) => {
    await page.goto('/');
    await page.locator('input[type="file"]').setInputFiles({
      name: 'acme-msa.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 fake'),
    });
    await expect(page).toHaveURL(/\/review\/doc-789$/, { timeout: 10_000 });

    // Navigate to Client summary.
    await page.getByTestId('tab-summary').click();
    await expect(page.getByTestId('summary-disclaimer')).toBeVisible();

    // Tamper: remove the node from the DOM.
    await page.evaluate(() => {
      document
        .querySelector('[data-testid="summary-disclaimer"]')
        ?.remove();
    });
    // Confirm the tamper actually worked at this moment.
    await expect(page.getByTestId('summary-disclaimer')).toHaveCount(0);

    // Trigger a small state change so the component re-renders: toggle Edit
    // on the "What this contract is" section, then Cancel.
    await page.getByTestId('edit-what_this_contract_is').click();
    await page.getByTestId('cancel-what_this_contract_is').click();

    // Constitution IV pinned: the disclaimer block is back.
    await expect(page.getByTestId('summary-disclaimer')).toBeVisible();
    await expect(page.getByTestId('summary-disclaimer')).toHaveText(
      ANALYZE_BODY.client_summary.disclaimer,
    );
  });
});
