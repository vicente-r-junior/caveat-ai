import { expect, test } from '@playwright/test';

// Sprint 3 fixup-2 — analyze call-count regression test.
//
// The bug: a real upload of nda-techcorp.pdf produced TWO POST /api/analyze
// requests in the backend log. Root cause: React 18 StrictMode's intentional
// dev double-mount re-fired the analyze effect on the second mount, and
// neither Processing.tsx nor Review.tsx held a ref-guard that survived the
// remount.
//
// The fix (just landed): both pages now hold a `fetchedForDocIdRef` set
// *before* the fetch dispatch and checked at the top of the effect. The
// second mount short-circuits without dispatching a second POST.
//
// This test pins that invariant at the browser layer — the only place that
// faithfully replicates Vite-dev StrictMode behavior with real `fetch`.
// jsdom + vitest cannot prove the same thing because the React act() loop
// there does not reproduce the StrictMode mount/cleanup/mount sequence
// against a real network call.
//
// Mechanism note: `page.on('request', ...)` fires for every request the
// browser dispatches, *before* `page.route()` decides whether to fulfill
// or abort. The captured-request list therefore reflects how many times
// the browser actually attempted the call — which is exactly the
// StrictMode duplication signal we need.
//
// All routes are mocked so the test runs without a backend or Ollama.

const ANALYZE_BODY = {
  document_id: 'doc-count',
  contract_type: null,
  findings: [],
  client_summary: {
    what_this_contract_is: '',
    what_youre_committing_to: '',
    biggest_risks: [],
    recommendation: '',
    disclaimer:
      'AI-generated output — attorney review required. Caveat AI is a tool, not legal advice.',
  },
  warnings: [],
  elapsed_seconds: 0.5,
  source_sections: [],
};

test.describe('Sprint 3 fixup-2 — POST /api/analyze fires exactly once', () => {
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
            document_id: 'doc-count',
            filename: 'count-test.pdf',
            page_count: 4,
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
    await page.route('**/api/analyze/doc-count', async (route) => {
      // Small delay so any StrictMode-driven duplicate has a chance to
      // dispatch before the response lands.
      await new Promise((r) => setTimeout(r, 200));
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(ANALYZE_BODY),
      });
    });
  });

  test('upload → processing → review dispatches POST /api/analyze/{id} exactly once', async ({
    page,
  }) => {
    // Count every analyze request the browser dispatches. This fires
    // independent of (and before) page.route()'s fulfill/abort decision.
    const analyzeRequests: string[] = [];
    page.on('request', (req) => {
      if (req.method() !== 'POST') return;
      const url = new URL(req.url());
      if (/^\/api\/analyze\/[^/]+$/.test(url.pathname)) {
        analyzeRequests.push(url.pathname);
      }
    });

    // 1. Land on Upload.
    await page.goto('/');

    // 2. Drop a synthetic PDF. The buffer contents are irrelevant — the
    // POST /api/documents/ route is mocked and returns doc-count.
    await page.locator('input[type="file"]').setInputFiles({
      name: 'count-test.pdf',
      mimeType: 'application/pdf',
      buffer: Buffer.from('%PDF-1.4 fake'),
    });

    // 3. Wait for the Review URL — confirms Processing → Review handoff
    // completed.
    await expect(page).toHaveURL(/\/review\/doc-count$/, { timeout: 10_000 });

    // 4. Settle window: catch any late StrictMode-driven duplicate that
    // could fire after the Review component mounts.
    await page.waitForTimeout(500);

    // 5. Pin the invariant: exactly one POST /api/analyze/{id}.
    expect(
      analyzeRequests,
      `Expected exactly one POST /api/analyze/{id} request; captured ${analyzeRequests.length}: ${JSON.stringify(analyzeRequests)}`,
    ).toHaveLength(1);
    expect(analyzeRequests[0]).toBe('/api/analyze/doc-count');
  });
});
