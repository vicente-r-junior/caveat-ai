/**
 * Findings tab tests — Sprint 2 / US1.
 *
 * THE most important Sprint 2 test file: pins Constitution VI in the UI.
 *
 *   - When the model returns warnings, the banner renders verbatim ABOVE
 *     the summary cards.
 *   - When findings=[] but warnings present, the empty state must NEVER
 *     read "no risks found" or "safe" — Constitution VI demands honest
 *     uncertainty over false reassurance.
 *
 * The component is pure on props — no router needed.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Findings } from './Findings';
import type { AnalyzeResponse, Finding, Severity } from '../api/analyze';

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    severity: 'medium',
    title: 'A finding',
    quote: 'A literal quotation from the contract.',
    explanation: 'Why it matters.',
    redline: '',
    ...overrides,
  };
}

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
    ...overrides,
  };
}

describe('<Findings />', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  // -----------------------------------------------------------------
  // (a) HAPPY PATH
  // -----------------------------------------------------------------
  it('happy path: 3 findings, no warnings → 3 cards, no banner, summary counts correct', () => {
    const analysis = makeAnalysis({
      findings: [
        makeFinding({
          severity: 'high',
          title: 'High one',
          quote: 'high quote',
        }),
        makeFinding({
          severity: 'medium',
          title: 'Med one',
          quote: 'med quote',
        }),
        makeFinding({
          severity: 'missing',
          title: 'Missing one',
          quote: 'missing quote',
        }),
      ],
      warnings: [],
      elapsed_seconds: 12.3,
    });

    render(<Findings analysis={analysis} />);

    expect(screen.getAllByTestId('finding-card')).toHaveLength(3);
    expect(screen.queryByTestId('warnings-banner')).toBeNull();

    const summary = screen.getByTestId('findings-summary');
    expect(summary).toHaveTextContent(/High risk/i);
    expect(summary).toHaveTextContent(/Medium/i);
    expect(summary).toHaveTextContent(/Missing clauses/i);
    expect(summary).toHaveTextContent(/Analysis time/i);
    // Counts: 1, 1, 1, 12.3s
    expect(summary).toHaveTextContent(/12\.3s/);
  });

  // -----------------------------------------------------------------
  // (b) WARNINGS PRESENT — banner appears ABOVE summary cards
  // -----------------------------------------------------------------
  it('warnings present: banner renders ABOVE the summary cards with verbatim text', () => {
    const warning =
      'Citation validation dropped 2 of 5 findings on the first attempt; second attempt produced fewer.';
    const analysis = makeAnalysis({
      findings: [
        makeFinding({ severity: 'high', title: 'A', quote: 'q1' }),
        makeFinding({ severity: 'medium', title: 'B', quote: 'q2' }),
      ],
      warnings: [warning],
    });

    render(<Findings analysis={analysis} />);

    const banner = screen.getByTestId('warnings-banner');
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent(warning);

    const summary = screen.getByTestId('findings-summary');

    // DOM ORDER: banner must precede summary.
    // Node.compareDocumentPosition returns 4 (DOCUMENT_POSITION_FOLLOWING)
    // when the second arg follows the first.
    // eslint-disable-next-line no-bitwise
    const followingMask = Node.DOCUMENT_POSITION_FOLLOWING;
    expect(
      // eslint-disable-next-line no-bitwise
      banner.compareDocumentPosition(summary) & followingMask,
    ).toBeTruthy();
  });

  // -----------------------------------------------------------------
  // (c) HONEST EMPTY STATE WITH WARNINGS — no false reassurance
  // -----------------------------------------------------------------
  it('honest empty state: findings=[] + warnings → "Analysis incomplete", NO "no risks", NO "safe"', () => {
    const analysis = makeAnalysis({
      findings: [],
      warnings: [
        'model returned 0 findings',
        'client summary placeholders',
      ],
    });

    render(<Findings analysis={analysis} />);

    const banner = screen.getByTestId('warnings-banner');
    expect(banner).toHaveTextContent('model returned 0 findings');
    expect(banner).toHaveTextContent('client summary placeholders');

    const empty = screen.getByTestId('findings-empty-with-warnings');
    expect(empty).toBeInTheDocument();
    expect(empty).toHaveTextContent(/Analysis incomplete/i);

    // THE NEGATIVES — Constitution VI made tangible.
    expect(screen.queryByText(/no risks/i)).toBeNull();
    expect(screen.queryByText(/safe/i)).toBeNull();
    expect(screen.queryByTestId('findings-empty-clean')).toBeNull();
  });

  // -----------------------------------------------------------------
  // (d) TRULY EMPTY + NO WARNINGS — clean empty state (still honest)
  // -----------------------------------------------------------------
  it('truly empty + no warnings: clean empty state, mentions "review manually", still no false reassurance', () => {
    const analysis = makeAnalysis({ findings: [], warnings: [] });

    render(<Findings analysis={analysis} />);

    expect(screen.queryByTestId('warnings-banner')).toBeNull();
    const clean = screen.getByTestId('findings-empty-clean');
    expect(clean).toBeInTheDocument();
    expect(clean).toHaveTextContent(/review manually/i);

    // Even the "clean" branch must NOT use the words "no risks" — those
    // would falsely reassure. Constitution VI.
    expect(screen.queryByText(/no risks/i)).toBeNull();
  });

  // -----------------------------------------------------------------
  // (e) SEVERITY BADGES
  // -----------------------------------------------------------------
  it('severity badges: each variant gets the right data-severity and Tailwind class', () => {
    const severities: Severity[] = ['high', 'medium', 'low', 'missing'];
    const expectedBg: Record<Severity, string> = {
      high: 'bg-danger',
      medium: 'bg-warn',
      low: 'bg-gold',
      missing: 'bg-ink',
    };

    const analysis = makeAnalysis({
      findings: severities.map((sev, i) =>
        makeFinding({
          severity: sev,
          title: `Title ${i}`,
          quote: `Quote ${i}`,
        }),
      ),
    });

    render(<Findings analysis={analysis} />);

    const badges = screen.getAllByTestId('severity-badge');
    expect(badges).toHaveLength(4);
    badges.forEach((badge, i) => {
      const sev = severities[i]!;
      expect(badge).toHaveAttribute('data-severity', sev);
      expect(badge.className).toContain(expectedBg[sev]);
    });
  });

  // -----------------------------------------------------------------
  // (f) ACCEPT TOGGLES STATE
  // -----------------------------------------------------------------
  it('accept toggles state: ✓ Accept → ✓ Accepted → ✓ Accept; data-state matches', async () => {
    const analysis = makeAnalysis({
      findings: [makeFinding({ severity: 'high', title: 'A', quote: 'q' })],
    });

    render(<Findings analysis={analysis} />);

    const card = screen.getByTestId('finding-card');
    expect(card).toHaveAttribute('data-state', 'pending');
    const acceptBtn = screen.getByTestId('finding-accept');
    expect(acceptBtn).toHaveTextContent('✓ Accept');

    await userEvent.click(acceptBtn);
    expect(screen.getByTestId('finding-card')).toHaveAttribute(
      'data-state',
      'accepted',
    );
    expect(screen.getByTestId('finding-accept')).toHaveTextContent(
      '✓ Accepted',
    );

    // Second click reverts.
    await userEvent.click(screen.getByTestId('finding-accept'));
    expect(screen.getByTestId('finding-card')).toHaveAttribute(
      'data-state',
      'pending',
    );
    expect(screen.getByTestId('finding-accept')).toHaveTextContent(
      '✓ Accept',
    );
  });

  // -----------------------------------------------------------------
  // (g) DISMISS HIDES
  // -----------------------------------------------------------------
  it('dismiss hides the card from the rendered list', async () => {
    const analysis = makeAnalysis({
      findings: [
        makeFinding({ severity: 'high', title: 'A', quote: 'qa' }),
        makeFinding({ severity: 'medium', title: 'B', quote: 'qb' }),
        makeFinding({ severity: 'missing', title: 'C', quote: 'qc' }),
      ],
    });

    render(<Findings analysis={analysis} />);

    expect(screen.getAllByTestId('finding-card')).toHaveLength(3);
    const dismissButtons = screen.getAllByTestId('finding-dismiss');
    await userEvent.click(dismissButtons[1]!); // dismiss B

    const remaining = screen.getAllByTestId('finding-card');
    expect(remaining).toHaveLength(2);
    expect(screen.queryByText('B')).toBeNull();
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('C')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------
  // (h) FILTER CHIPS WORK
  // -----------------------------------------------------------------
  it('filter chips: "High only" hides medium and missing; "All" restores them', async () => {
    const analysis = makeAnalysis({
      findings: [
        makeFinding({ severity: 'high', title: 'High one', quote: 'q1' }),
        makeFinding({ severity: 'medium', title: 'Med one', quote: 'q2' }),
        makeFinding({ severity: 'missing', title: 'Missing one', quote: 'q3' }),
      ],
    });

    render(<Findings analysis={analysis} />);

    expect(screen.getAllByTestId('finding-card')).toHaveLength(3);

    await userEvent.click(screen.getByRole('button', { name: /High only/i }));
    expect(screen.getAllByTestId('finding-card')).toHaveLength(1);
    expect(screen.getByText('High one')).toBeInTheDocument();
    expect(screen.queryByText('Med one')).toBeNull();
    expect(screen.queryByText('Missing one')).toBeNull();

    await userEvent.click(screen.getByRole('button', { name: /^All 3$/ }));
    expect(screen.getAllByTestId('finding-card')).toHaveLength(3);
  });

  // -----------------------------------------------------------------
  // (i) ACCEPTED FILTER CHIP COUNT
  // -----------------------------------------------------------------
  it('Accepted (N) chip count updates as findings are accepted', async () => {
    const analysis = makeAnalysis({
      findings: [
        makeFinding({ severity: 'high', title: 'A', quote: 'qa' }),
        makeFinding({ severity: 'medium', title: 'B', quote: 'qb' }),
        makeFinding({ severity: 'missing', title: 'C', quote: 'qc' }),
      ],
    });

    render(<Findings analysis={analysis} />);

    // Initial count is zero.
    expect(
      screen.getByRole('button', { name: /Accepted \(0\)/ }),
    ).toBeInTheDocument();

    const accepts = screen.getAllByTestId('finding-accept');
    await userEvent.click(accepts[0]!);
    await userEvent.click(accepts[1]!);

    expect(
      screen.getByRole('button', { name: /Accepted \(2\)/ }),
    ).toBeInTheDocument();

    // Clicking the chip filters to the accepted set (2 cards).
    await userEvent.click(
      screen.getByRole('button', { name: /Accepted \(2\)/ }),
    );
    expect(screen.getAllByTestId('finding-card')).toHaveLength(2);
  });

  // -----------------------------------------------------------------
  // (j) CITATION BLOCK VISIBLE — Constitution II made tangible
  // -----------------------------------------------------------------
  it('citation block: every finding renders a finding-quote with the verbatim quote', () => {
    const analysis = makeAnalysis({
      findings: [
        makeFinding({
          severity: 'high',
          title: 'A',
          quote: 'The verbatim quotation about liability cap.',
        }),
        makeFinding({
          severity: 'medium',
          title: 'B',
          quote: 'A different exact passage about termination.',
        }),
      ],
    });

    render(<Findings analysis={analysis} />);

    const quotes = screen.getAllByTestId('finding-quote');
    expect(quotes).toHaveLength(2);
    expect(quotes[0]!).toHaveTextContent(
      'The verbatim quotation about liability cap.',
    );
    expect(quotes[1]!).toHaveTextContent(
      'A different exact passage about termination.',
    );
  });

  // -----------------------------------------------------------------
  // (k) REDLINE ONLY WHEN PRESENT
  // -----------------------------------------------------------------
  it('redline: only renders when redline is non-empty; eyebrow says "Suggested redline"', () => {
    const noRedline = makeAnalysis({
      findings: [
        makeFinding({ severity: 'high', title: 'A', quote: 'q', redline: '' }),
      ],
    });
    const { unmount } = render(<Findings analysis={noRedline} />);
    expect(screen.queryByTestId('finding-redline')).toBeNull();
    unmount();

    const withRedline = makeAnalysis({
      findings: [
        makeFinding({
          severity: 'high',
          title: 'A',
          quote: 'q',
          redline: 'Replace 3 months with 12 months.',
        }),
      ],
    });
    render(<Findings analysis={withRedline} />);
    const redline = screen.getByTestId('finding-redline');
    expect(redline).toBeInTheDocument();
    expect(redline).toHaveTextContent(/Suggested redline/i);
    expect(redline).toHaveTextContent('Replace 3 months with 12 months.');
  });
});
