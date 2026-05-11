/**
 * Processing → Review handoff — Sprint 3 fixup-1 regression test.
 *
 * The bug: a single upload of msa-acme.pdf produced TWO POST /api/analyze
 * calls in the backend log. The cause was Review.tsx unconditionally
 * re-firing analyzeDocument on mount, ignoring the analysis that
 * Processing.tsx already had in hand and passed through router state.
 *
 * This test pins the post-fix invariant: across the full Processing → Review
 * transition, `analyzeDocument` is called **exactly once** (by Processing —
 * Review now skips the fetch when state.analysis is populated).
 *
 * Strategy: drive the real router. Processing fires the (mocked) fetch and
 * navigates to /review/{id} with state.analysis populated. Review mounts,
 * sees the preloaded analysis, renders without fetching. Counter on the
 * mock proves exactly-one.
 */

import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, Outlet } from 'react-router-dom';

vi.mock('../api/analyze', () => ({
  analyzeDocument: vi.fn(),
}));

import { Processing } from './Processing';
import { Review } from './Review';
import { analyzeDocument, type AnalyzeResponse } from '../api/analyze';

function makeAnalysis(): AnalyzeResponse {
  return {
    document_id: 'abc',
    contract_type: 'MSA',
    findings: [],
    client_summary: {
      what_this_contract_is: 'An MSA.',
      what_youre_committing_to: 'Services.',
      biggest_risks: ['Low cap.'],
      recommendation: 'Negotiate.',
      disclaimer: 'AI-generated output — attorney review required.',
    },
    warnings: [],
    elapsed_seconds: 1.2,
    source_sections: [],
  };
}

function OutletShell(): JSX.Element {
  const ctx = {
    setActiveDoc: () => undefined,
    setStatus: () => undefined,
  };
  return <Outlet context={ctx} />;
}

describe('Processing → Review handoff (fixup-1)', () => {
  beforeEach(() => {
    vi.mocked(analyzeDocument).mockReset();
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('fires analyzeDocument exactly once across the full Processing → Review transition', async () => {
    const analysis = makeAnalysis();
    // Manually-resolvable promise so the test can drain inside act().
    let resolveFn: (val: AnalyzeResponse) => void = () => undefined;
    const pending = new Promise<AnalyzeResponse>((resolve) => {
      resolveFn = resolve;
    });
    vi.mocked(analyzeDocument).mockReturnValue(pending);

    render(
      <StrictMode>
        <MemoryRouter
          initialEntries={[
            {
              pathname: '/processing/abc',
              state: { filename: 'test.pdf', pageCount: 8 },
            },
          ]}
        >
          <Routes>
            <Route element={<OutletShell />}>
              <Route path="/processing/:docId" element={<Processing />} />
              <Route path="/review/:docId" element={<Review />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </StrictMode>,
    );

    // Processing kicked off exactly one fetch.
    expect(analyzeDocument).toHaveBeenCalledTimes(1);

    // Resolve. Processing fast-forwards stages → navigates to /review/abc
    // with state.analysis carried through.
    await act(async () => {
      resolveFn(analysis);
      await pending;
    });

    // Review is now mounted with the preloaded analysis. Findings renders
    // synchronously off the preloaded state — no spinner, no second fetch.
    expect(screen.getByTestId('findings-wrap')).toBeInTheDocument();

    // Drain a microtask in case a stray effect was scheduled.
    await Promise.resolve();

    // The post-fix invariant: still exactly one call total.
    expect(analyzeDocument).toHaveBeenCalledTimes(1);
  });
});
