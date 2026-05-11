/**
 * Processing page tests — Sprint 2 / US1.
 *
 * Covers the 6-stage timer-driven UI, the cold-start sub-line copy
 * (Constitution VI), the fast-forward / hold-pulse contract, and the
 * verbatim error pane.
 *
 * Strategy:
 *   - Mock useNavigate + useLocation from react-router-dom.
 *   - Mock ../api/analyze so each test can decide resolve / reject /
 *     never-resolve.
 *   - Use vi.useFakeTimers() per test and pump time deterministically.
 */

import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, Outlet } from 'react-router-dom';

const navigateMock = vi.fn();

vi.mock('react-router-dom', async (importOriginal) => {
  const mod =
    await importOriginal<typeof import('react-router-dom')>();
  return {
    ...mod,
    useNavigate: () => navigateMock,
  };
});

vi.mock('../api/analyze', () => ({
  analyzeDocument: vi.fn(),
}));

import { Processing } from './Processing';
import { ApiError } from '../api/client';
import { analyzeDocument, type AnalyzeResponse } from '../api/analyze';

function makeAnalysis(
  overrides: Partial<AnalyzeResponse> = {},
): AnalyzeResponse {
  return {
    document_id: 'abc',
    contract_type: 'MSA',
    findings: [],
    client_summary: {
      what_this_contract_is: '',
      what_youre_committing_to: '',
      biggest_risks: [],
      recommendation: '',
      disclaimer: 'AI-generated output — attorney review required.',
    },
    warnings: [],
    elapsed_seconds: 1.5,
    source_sections: [],
    ...overrides,
  };
}

function OutletShell(): JSX.Element {
  const ctx = {
    setActiveDoc: () => undefined,
    setStatus: () => undefined,
  };
  return <Outlet context={ctx} />;
}

function renderProcessing(state?: { filename: string; pageCount?: number }): void {
  render(
    <MemoryRouter
      initialEntries={[
        { pathname: '/processing/abc', state: state ?? null },
      ]}
    >
      <Routes>
        <Route element={<OutletShell />}>
          <Route path="/processing/:docId" element={<Processing />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('<Processing />', () => {
  beforeEach(() => {
    navigateMock.mockReset();
    vi.mocked(analyzeDocument).mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('renders all 6 pipeline stages with the prototype copy', () => {
    vi.mocked(analyzeDocument).mockImplementation(
      () => new Promise(() => undefined),
    );
    renderProcessing({ filename: 'test.pdf', pageCount: 8 });

    expect(
      screen.getByText(/Parse PDF and extract structured sections/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Classify contract type/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Load playbook from local library/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Identify risk clauses and missing provisions/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Validate citations against source text/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Generate plain-English client summary/i),
    ).toBeInTheDocument();
  });

  it('starts with stage 0 (parse) active and the rest pending', () => {
    vi.mocked(analyzeDocument).mockImplementation(
      () => new Promise(() => undefined),
    );
    renderProcessing({ filename: 'test.pdf' });

    expect(screen.getByTestId('pipe-step-parse')).toHaveAttribute(
      'data-status',
      'active',
    );
    expect(screen.getByTestId('pipe-step-classify')).toHaveAttribute(
      'data-status',
      'pending',
    );
    expect(screen.getByTestId('pipe-step-summary')).toHaveAttribute(
      'data-status',
      'pending',
    );
  });

  it('advances stages on the timer (Parse → done, Classify → active)', () => {
    vi.useFakeTimers();
    vi.mocked(analyzeDocument).mockImplementation(
      () => new Promise(() => undefined),
    );
    renderProcessing({ filename: 'test.pdf' });

    expect(screen.getByTestId('pipe-step-parse')).toHaveAttribute(
      'data-status',
      'active',
    );

    act(() => {
      vi.advanceTimersByTime(1500);
    });

    expect(screen.getByTestId('pipe-step-parse')).toHaveAttribute(
      'data-status',
      'done',
    );
    expect(screen.getByTestId('pipe-step-classify')).toHaveAttribute(
      'data-status',
      'active',
    );
  });

  it('renders the cold-start sub-line copy verbatim (Constitution VI)', () => {
    vi.mocked(analyzeDocument).mockImplementation(
      () => new Promise(() => undefined),
    );
    renderProcessing({ filename: 'test.pdf' });

    // Spec wording — "First analysis after starting may take 3–5 min" with
    // a unicode en-dash. Match a stable substring of it (case-sensitive).
    expect(
      screen.getByText(
        /First analysis after starting may take 3–5 min while Gemma loads into RAM/,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/subsequent analyses are 30–120s/),
    ).toBeInTheDocument();
  });

  it('on success: marks all stages done and navigates to /review/{docId}', async () => {
    const analysis = makeAnalysis({ document_id: 'abc' });
    // Manually-resolvable promise so we can drain the microtask inside act().
    let resolveFn: (val: AnalyzeResponse) => void = () => undefined;
    const pending = new Promise<AnalyzeResponse>((resolve) => {
      resolveFn = resolve;
    });
    vi.mocked(analyzeDocument).mockReturnValue(pending);

    renderProcessing({ filename: 'test.pdf', pageCount: 8 });

    await act(async () => {
      resolveFn(analysis);
      await pending;
    });

    expect(navigateMock).toHaveBeenCalledWith('/review/abc', {
      replace: true,
      state: { analysis, filename: 'test.pdf' },
    });

    // Each stage is done after fast-forward.
    for (const key of [
      'parse',
      'classify',
      'playbook',
      'analyze',
      'validate',
      'summary',
    ]) {
      expect(screen.getByTestId(`pipe-step-${key}`)).toHaveAttribute(
        'data-status',
        'done',
      );
    }
  });

  it('on 503 reject: shows verbatim error pane + Back to upload, no nav', async () => {
    vi.mocked(analyzeDocument).mockRejectedValue(
      new ApiError(
        'Ollama unreachable: please start `ollama serve`',
        503,
      ),
    );

    renderProcessing({ filename: 'test.pdf' });

    const errorPane = await screen.findByTestId('processing-error');
    expect(errorPane).toHaveTextContent(
      /Ollama unreachable: please start `ollama serve`/,
    );
    expect(
      screen.getByRole('link', { name: /Back to upload/i }),
    ).toHaveAttribute('href', '/');
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it('does not double-fire analyzeDocument under StrictMode', async () => {
    // Sprint 3 fixup-2: the dedupe `fetchedForDocIdRef` in Processing.tsx
    // must short-circuit StrictMode's intentional dev double-mount of the
    // analyze effect. A never-resolving promise lets us count call
    // dispatches without inducing navigation or stage advancement.
    vi.mocked(analyzeDocument).mockImplementation(
      () => new Promise(() => undefined),
    );

    render(
      <StrictMode>
        <MemoryRouter
          initialEntries={[{ pathname: '/processing/abc', state: { filename: 'test.pdf' } }]}
        >
          <Routes>
            <Route element={<OutletShell />}>
              <Route path="/processing/:docId" element={<Processing />} />
            </Route>
          </Routes>
        </MemoryRouter>
      </StrictMode>,
    );

    // Drain microtasks so any effect-scheduled fetch would have landed.
    await Promise.resolve();
    await Promise.resolve();

    expect(analyzeDocument).toHaveBeenCalledTimes(1);
  });

  it('hold-pulse: never auto-completes the last stage on the timer alone', () => {
    vi.useFakeTimers();
    vi.mocked(analyzeDocument).mockImplementation(
      () => new Promise(() => undefined),
    );

    renderProcessing({ filename: 'test.pdf' });

    // Each stage schedules its own setTimeout in a useEffect that re-runs
    // when currentStage changes; we have to give React a render cycle
    // between ticks so the next stage's timer is registered. Walk the full
    // ladder explicitly: parse → classify → playbook → analyze → validate
    // → summary (LAST stage). After this the LAST stage must be active and
    // STAY active because the implementation MUST NOT auto-complete it.
    const stageDurations = [1500, 5000, 500, 70000, 2000];
    for (const ms of stageDurations) {
      act(() => {
        vi.advanceTimersByTime(ms);
      });
    }

    expect(screen.getByTestId('pipe-step-summary')).toHaveAttribute(
      'data-status',
      'active',
    );

    // Now drive WAY past the last stage's nominal dwell time. The honest
    // contract is that we never mark "summary" done on the timer alone.
    act(() => {
      vi.advanceTimersByTime(120_000);
    });

    expect(screen.getByTestId('pipe-step-summary')).toHaveAttribute(
      'data-status',
      'active',
    );
    expect(navigateMock).not.toHaveBeenCalled();
  });
});
