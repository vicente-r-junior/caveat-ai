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

  it('clicking Client summary switches to the Sprint 3 placeholder', async () => {
    renderReview({
      analysis: makeAnalysis(),
      filename: 'acme-msa.pdf',
    });
    await userEvent.click(screen.getByTestId('tab-summary'));
    const placeholder = await screen.findByTestId('tab-placeholder');
    expect(placeholder).toHaveTextContent(/Coming in Sprint 3/);
    expect(placeholder).toHaveTextContent(/Client summary/);
    expect(screen.queryByTestId('findings-wrap')).toBeNull();
  });

  it('clicking Source switches to the Sprint 3 placeholder (Source viewer)', async () => {
    renderReview({
      analysis: makeAnalysis(),
      filename: 'acme-msa.pdf',
    });
    await userEvent.click(screen.getByTestId('tab-source'));
    const placeholder = await screen.findByTestId('tab-placeholder');
    expect(placeholder).toHaveTextContent(/Coming in Sprint 3/);
    expect(placeholder).toHaveTextContent(/Source viewer/);
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
});
