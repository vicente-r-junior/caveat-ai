/**
 * Review page tests — Sprint 2 / US1.
 *
 * Covers: sidebar with document, tab bar with 4 tabs (Findings active by
 * default), tab switching to TabPlaceholder for Sprint 3 / 4 stubs, the
 * disabled Re-analyze and Add document buttons with their roadmap titles,
 * and the privacy footer in the sidebar.
 *
 * The page can re-fetch via analyzeDocument when location.state is empty,
 * so we mock that to a resolved value and pass full state to suppress it.
 */

import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Outlet, Route, Routes } from 'react-router-dom';

vi.mock('../api/analyze', () => ({
  analyzeDocument: vi.fn(),
}));

import { Review } from './Review';
import { analyzeDocument, type AnalyzeResponse } from '../api/analyze';

function makeAnalysis(
  overrides: Partial<AnalyzeResponse> = {},
): AnalyzeResponse {
  return {
    document_id: 'abc',
    contract_type: 'MSA',
    findings: [
      {
        severity: 'high',
        title: 'Liability cap dangerously low',
        quote: 'In no event shall liability exceed three months of fees.',
        explanation: 'A 3-month cap is well below market.',
        redline: 'Replace with twelve months.',
        source_offset: null,
      },
    ],
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
    ...overrides,
  };
}

function makeAnalysisWithSource(): AnalyzeResponse {
  // Section 0 body starts at char 0 with quote at offset 0–5.
  // Section 1 is empty of highlights.
  return makeAnalysis({
    findings: [
      {
        severity: 'high',
        title: 'Liability cap dangerously low',
        quote: 'Quote',
        explanation: 'Why.',
        redline: '',
        source_offset: { section_index: 0, start: 0, end: 5 },
      },
    ],
    source_sections: [
      {
        idx: 0,
        number: '4.2',
        title: 'Limitation of Liability',
        body: 'Quote here.',
        char_start: 0,
        char_end: 11,
        page: 1,
      },
      {
        idx: 1,
        number: '5.1',
        title: 'Indemnification',
        body: 'No highlights here.',
        char_start: 100,
        char_end: 119,
        page: 1,
      },
    ],
  });
}

function OutletShell(): JSX.Element {
  const ctx = {
    setActiveDoc: () => undefined,
    setStatus: () => undefined,
  };
  return <Outlet context={ctx} />;
}

function renderReview(state: {
  analysis: AnalyzeResponse;
  filename: string;
}): void {
  render(
    <MemoryRouter
      initialEntries={[
        { pathname: '/review/abc', state },
      ]}
    >
      <Routes>
        <Route element={<OutletShell />}>
          <Route path="/review/:docId" element={<Review />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

function renderReviewWithoutState(): void {
  render(
    <MemoryRouter
      initialEntries={[{ pathname: '/review/abc', state: null }]}
    >
      <Routes>
        <Route element={<OutletShell />}>
          <Route path="/review/:docId" element={<Review />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('<Review />', () => {
  beforeEach(() => {
    // Re-fetch path should never be hit when state is provided; mock a stub
    // anyway in case future regression triggers it.
    vi.mocked(analyzeDocument).mockResolvedValue(makeAnalysis());
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('sidebar shows the document with "Documents · 1" label and filename', () => {
    renderReview({
      analysis: makeAnalysis(),
      filename: 'acme-msa.pdf',
    });
    // The "Documents" eyebrow + the "1" count live next to each other in
    // the sidebar — find the count via its parent's accessible neighbor.
    const docsLabel = screen.getByText(/Documents/i);
    expect(docsLabel).toBeInTheDocument();
    expect(docsLabel.parentElement).toHaveTextContent(/^Documents1$/);
    expect(
      screen.getByTestId('sidebar-doc-active'),
    ).toHaveTextContent('acme-msa.pdf');
  });

  it('tab bar renders 4 tabs: Findings (active), Client summary, Source, Chat', () => {
    renderReview({
      analysis: makeAnalysis(),
      filename: 'acme-msa.pdf',
    });
    expect(screen.getByTestId('tab-findings')).toHaveTextContent(/Findings/i);
    expect(screen.getByTestId('tab-summary')).toHaveTextContent(
      /Client summary/i,
    );
    expect(screen.getByTestId('tab-source')).toHaveTextContent(/Source/i);
    expect(screen.getByTestId('tab-chat')).toHaveTextContent(/Chat/i);
    // Findings active by default.
    expect(screen.getByTestId('tab-findings')).toHaveAttribute(
      'aria-current',
      'page',
    );
    expect(screen.getByTestId('tab-summary')).not.toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('default active tab content is Findings', () => {
    renderReview({
      analysis: makeAnalysis(),
      filename: 'acme-msa.pdf',
    });
    // Findings wrap shows up; placeholder pane does not.
    expect(screen.getByTestId('findings-wrap')).toBeInTheDocument();
    expect(screen.queryByTestId('tab-placeholder')).toBeNull();
  });

  it('clicking Client summary switches to the live Sprint 3 ClientSummary tab', async () => {
    renderReview({
      analysis: makeAnalysis(),
      filename: 'acme-msa.pdf',
    });
    await userEvent.click(screen.getByTestId('tab-summary'));
    // ClientSummary renders the prototype's "actually reads." copy and the
    // "What this contract is" section heading.
    expect(await screen.findByText(/actually reads\./i)).toBeInTheDocument();
    expect(screen.getByText('What this contract is')).toBeInTheDocument();
    // Sprint 3 placeholder copy is gone for this tab.
    expect(screen.queryByText(/Coming in Sprint 3/)).toBeNull();
    expect(screen.queryByTestId('findings-wrap')).toBeNull();
  });

  it('clicking Source switches to the live Sprint 3 Source tab with section headings from analysis', async () => {
    renderReview({
      analysis: makeAnalysisWithSource(),
      filename: 'acme-msa.pdf',
    });
    await userEvent.click(screen.getByTestId('tab-source'));
    // The Source tab renders at least one section heading from analysis.source_sections.
    expect(
      await screen.findByRole('heading', {
        level: 3,
        name: 'Limitation of Liability',
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 3, name: 'Indemnification' }),
    ).toBeInTheDocument();
    // Sprint 3 placeholder copy is gone for this tab.
    expect(screen.queryByText(/Coming in Sprint 3/)).toBeNull();
  });

  it('clicking Chat switches to the Sprint 4 placeholder', async () => {
    renderReview({
      analysis: makeAnalysis(),
      filename: 'acme-msa.pdf',
    });
    await userEvent.click(screen.getByTestId('tab-chat'));
    const placeholder = await screen.findByTestId('tab-placeholder');
    expect(placeholder).toHaveTextContent(/Coming in Sprint 4/);
    expect(placeholder).toHaveTextContent(/Multi-document chat/);
  });

  it('Re-analyze button is rendered, disabled, with title mentioning Sprint 5', () => {
    renderReview({
      analysis: makeAnalysis(),
      filename: 'acme-msa.pdf',
    });
    const btn = screen.getByTestId('tab-action-reanalyze');
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('title', expect.stringMatching(/Sprint 5/i));
  });

  it('sidebar privacy footer note is visible', () => {
    renderReview({
      analysis: makeAnalysis(),
      filename: 'acme-msa.pdf',
    });
    const note = screen.getByTestId('sidebar-privacy-note');
    expect(note).toBeInTheDocument();
    expect(note).toHaveTextContent(/Privileged work product/i);
    expect(note).toHaveTextContent(/Nothing leaves this machine/i);
  });

  it('Add document button is disabled with title mentioning Sprint 4', () => {
    renderReview({
      analysis: makeAnalysis(),
      filename: 'acme-msa.pdf',
    });
    const addBtn = screen.getByTestId('sidebar-add-doc');
    expect(addBtn).toBeDisabled();
    expect(addBtn).toHaveAttribute(
      'title',
      expect.stringMatching(/Sprint 4/i),
    );
  });

  // -----------------------------------------------------------------
  // Sprint 3 fixup-1 — preloaded analysis from router state skips re-fetch
  // -----------------------------------------------------------------
  it('preloaded analysis from router state skips the analyzeDocument fetch', async () => {
    renderReview({
      analysis: makeAnalysis(),
      filename: 'acme-msa.pdf',
    });
    // Findings renders synchronously off the preloaded state.
    expect(screen.getByTestId('findings-wrap')).toBeInTheDocument();
    // No call to analyzeDocument — the Processing → Review handoff is
    // honored. Wait a tick to be safe: any effect-scheduled fetch would
    // have landed by now.
    await Promise.resolve();
    expect(analyzeDocument).not.toHaveBeenCalled();
  });

  it('cold-mount with no router state triggers one analyzeDocument call', async () => {
    // Override the beforeEach auto-resolve with a never-resolving promise so
    // the in-flight spinner is observable and we can count calls deterministically.
    vi.mocked(analyzeDocument).mockImplementation(
      () => new Promise(() => undefined),
    );
    renderReviewWithoutState();
    // The "Re-running analysis" pane is visible while the fetch is in flight.
    expect(
      await screen.findByText(/Re-running the analysis on the local model/i),
    ).toBeInTheDocument();
    expect(analyzeDocument).toHaveBeenCalledTimes(1);
    expect(analyzeDocument).toHaveBeenCalledWith(
      'abc',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  // -----------------------------------------------------------------
  // Sprint 3 — Source tab badge shows section count (closes carry-forward note 8)
  // -----------------------------------------------------------------
  it('Source tab badge reflects analysis.source_sections.length', () => {
    renderReview({
      analysis: makeAnalysisWithSource(),
      filename: 'acme-msa.pdf',
    });
    const sourceTab = screen.getByTestId('tab-source');
    // 2 sections in the fixture.
    expect(sourceTab).toHaveTextContent(/2/);
  });

  // -----------------------------------------------------------------
  // Sprint 3 — Cross-tab jump: click highlight on Source → Findings + scroll
  // -----------------------------------------------------------------
  it('cross-tab jump: clicking a Source highlight flips activeTab to findings, marks the matching card, and calls scrollIntoView', async () => {
    // jsdom doesn't define scrollIntoView; install a stub so we can spy.
    if (!('scrollIntoView' in window.HTMLElement.prototype)) {
      Object.defineProperty(
        window.HTMLElement.prototype,
        'scrollIntoView',
        { configurable: true, writable: true, value: () => undefined },
      );
    }
    const scrollSpy = vi
      .spyOn(window.HTMLElement.prototype, 'scrollIntoView')
      .mockImplementation(() => undefined);

    try {
      renderReview({
        analysis: makeAnalysisWithSource(),
        filename: 'acme-msa.pdf',
      });

      // Start on Source tab. The Source content renders synchronously
      // when activeTab flips (no async data fetch in this code path).
      await userEvent.click(screen.getByTestId('tab-source'));
      const highlight = screen.getByTestId('source-highlight');

      // Click the highlight.
      await userEvent.click(highlight);

      // (a) activeTab flipped to findings — Findings content reappears.
      expect(screen.getByTestId('findings-wrap')).toBeInTheDocument();

      // (b) targeted finding card has data-finding-target="true" briefly.
      const card = screen.getByTestId('finding-card');
      expect(card).toHaveAttribute('data-finding-target', 'true');

      // (c) scrollIntoView called.
      expect(scrollSpy).toHaveBeenCalled();

      // After ~1500ms the data-finding-target attribute is auto-cleared.
      // Use real timers + waitFor to keep this honest without flakiness.
      await vi.waitFor(
        () => {
          expect(
            screen.getByTestId('finding-card'),
          ).not.toHaveAttribute('data-finding-target');
        },
        { timeout: 3000 },
      );
    } finally {
      scrollSpy.mockRestore();
    }
  });

  // -----------------------------------------------------------------
  // Sprint 3 fixup-2 — cold-mount under StrictMode does not double-fire
  // -----------------------------------------------------------------
  it('cold-mount under StrictMode dispatches exactly one analyzeDocument call', async () => {
    // The dedupe `fetchedForDocIdRef` in Review.tsx must short-circuit
    // StrictMode's intentional dev double-mount of the recover effect.
    // A never-resolving promise lets us count call dispatches deterministically.
    vi.mocked(analyzeDocument).mockImplementation(
      () => new Promise(() => undefined),
    );

    render(
      <StrictMode>
        <MemoryRouter initialEntries={[{ pathname: '/review/abc', state: null }]}>
          <Routes>
            <Route element={<OutletShell />}>
              <Route path="/review/:docId" element={<Review />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </StrictMode>,
    );

    await Promise.resolve();
    await Promise.resolve();

    expect(analyzeDocument).toHaveBeenCalledTimes(1);
  });
});
