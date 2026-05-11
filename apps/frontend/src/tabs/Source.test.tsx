/**
 * Source tab tests — Sprint 3 / US2.
 *
 * Pins Constitution III (no invented highlights — every <button> highlight
 * traces back to a finding's `source_offset`) and Constitution VI (un-located
 * quotes surface as a verbatim warning banner instead of being silently
 * dropped).
 *
 * Pins NFR-005 (every highlight is keyboard reachable + Enter-activatable
 * with an aria-label that names the target finding).
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Source } from './Source';
import type {
  AnalyzeResponse,
  Finding,
  Severity,
  SourceSection,
} from '../api/analyze';

function makeFinding(overrides: Partial<Finding> = {}): Finding {
  return {
    severity: 'medium',
    title: 'A finding',
    quote: 'A literal quotation from the contract.',
    explanation: 'Why it matters.',
    redline: '',
    source_offset: null,
    ...overrides,
  };
}

function makeSection(
  idx: number,
  number: string,
  title: string,
  body: string,
  charStart: number,
): SourceSection {
  return {
    idx,
    number,
    title,
    body,
    char_start: charStart,
    char_end: charStart + body.length,
    page: 1,
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
    elapsed_seconds: 1.0,
    source_sections: [],
    ...overrides,
  };
}

describe('<Source />', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  // -----------------------------------------------------------------
  // (a) HAPPY PATH — 3 sections, 2 highlights, no invented marks
  // -----------------------------------------------------------------
  it('happy path: 3 sections rendered in order; highlights only appear inside sections that own them', () => {
    // Section 0 body starts at char 0 ; "Liability cap quote" lives at offset 10–29.
    const body0 = 'Preamble. Liability cap quote ends here.';
    const section0 = makeSection(0, '4.2', 'Limitation of Liability', body0, 0);

    // Section 1 body starts at char 100, no findings.
    const body1 = 'Section without highlights.';
    const section1 = makeSection(1, '5.1', 'Indemnification', body1, 100);

    // Section 2 body starts at char 200; "Forfeit clause" lives at 210–224.
    const body2 = 'Termination. Forfeit clause is mean.';
    const section2 = makeSection(2, '7.3', 'Termination', body2, 200);

    const findings: Finding[] = [
      makeFinding({
        severity: 'high',
        title: 'Liability cap dangerously low',
        quote: 'Liability cap quote',
        source_offset: { section_index: 0, start: 10, end: 29 },
      }),
      makeFinding({
        severity: 'medium',
        title: 'Termination forfeits prepayments',
        quote: 'Forfeit clause',
        source_offset: { section_index: 2, start: 213, end: 227 },
      }),
    ];

    const analysis = makeAnalysis({
      findings,
      source_sections: [section0, section1, section2],
    });

    render(<Source analysis={analysis} onJumpToFinding={() => undefined} />);

    // Three section blocks, in order.
    const sections = screen.getAllByTestId('source-section');
    expect(sections).toHaveLength(3);
    expect(sections[0]!).toHaveTextContent('Limitation of Liability');
    expect(sections[1]!).toHaveTextContent('Indemnification');
    expect(sections[2]!).toHaveTextContent('Termination');

    // Section 0: one highlight for finding-index 0.
    const highlightsIn0 = within(sections[0]!).getAllByTestId('source-highlight');
    expect(highlightsIn0).toHaveLength(1);
    expect(highlightsIn0[0]!).toHaveAttribute('data-finding-index', '0');

    // Section 1: zero highlights (Constitution III — no invention).
    expect(
      within(sections[1]!).queryAllByTestId('source-highlight'),
    ).toHaveLength(0);

    // Section 2: one highlight for finding-index 1.
    const highlightsIn2 = within(sections[2]!).getAllByTestId('source-highlight');
    expect(highlightsIn2).toHaveLength(1);
    expect(highlightsIn2[0]!).toHaveAttribute('data-finding-index', '1');
  });

  // -----------------------------------------------------------------
  // (b) SEVERITY-TINTED CLASSES
  // -----------------------------------------------------------------
  it('severity-tinted classes: high/medium → danger-soft, low → warn-soft, missing → bg-tint', () => {
    // One section per severity, each with its own short body and one quote.
    const severities: Severity[] = ['high', 'medium', 'low', 'missing'];
    const expectedBg: Record<Severity, string> = {
      high: 'bg-danger-soft',
      medium: 'bg-danger-soft',
      low: 'bg-warn-soft',
      missing: 'bg-bg-tint',
    };

    const sections: SourceSection[] = severities.map((_, i) =>
      // Body: "QUOTE0 " + ... so the quote starts at offset 0 of the section's body.
      makeSection(i, String(i + 1), `Section ${i}`, `QUOTE${i} tail.`, i * 1000),
    );

    const findings: Finding[] = severities.map((sev, i) =>
      makeFinding({
        severity: sev,
        title: `Finding ${i}`,
        quote: `QUOTE${i}`,
        source_offset: {
          section_index: i,
          start: i * 1000,
          end: i * 1000 + `QUOTE${i}`.length,
        },
      }),
    );

    const analysis = makeAnalysis({ findings, source_sections: sections });
    render(<Source analysis={analysis} onJumpToFinding={() => undefined} />);

    const highlights = screen.getAllByTestId('source-highlight');
    expect(highlights).toHaveLength(4);
    highlights.forEach((h, i) => {
      const sev = severities[i]!;
      expect(h).toHaveAttribute('data-severity', sev);
      expect(h.className).toContain(expectedBg[sev]);
    });
  });

  // -----------------------------------------------------------------
  // (c) UN-LOCATED FINDING — warning banner, no <mark>
  // -----------------------------------------------------------------
  it('un-located finding: zero highlights rendered; warning surfaces verbatim above the source-doc', () => {
    const warningText =
      "Source viewer: finding 'Indemnification one-way' could not be located in the source text after citation validation. The Source tab will not show its highlight.";

    const section0 = makeSection(0, '5.1', 'Indemnification', 'Section body text.', 0);

    const analysis = makeAnalysis({
      findings: [
        makeFinding({
          severity: 'high',
          title: 'Indemnification one-way',
          source_offset: null,
        }),
      ],
      source_sections: [section0],
      warnings: [warningText],
    });

    render(<Source analysis={analysis} onJumpToFinding={() => undefined} />);

    // No highlights at all — Constitution III.
    expect(screen.queryAllByTestId('source-highlight')).toHaveLength(0);

    // Constitution VI banner is present, with the warning verbatim.
    const banner = screen.getByTestId('source-warnings-banner');
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent(warningText);

    // Banner appears BEFORE the source-doc block.
    const sourceDoc = screen.getByTestId('source-doc');
    // eslint-disable-next-line no-bitwise
    const followingMask = Node.DOCUMENT_POSITION_FOLLOWING;
    expect(
      // eslint-disable-next-line no-bitwise
      banner.compareDocumentPosition(sourceDoc) & followingMask,
    ).toBeTruthy();
  });

  // -----------------------------------------------------------------
  // (d) NO BANNER WHEN ONLY UNRELATED WARNINGS EXIST
  // -----------------------------------------------------------------
  it('non-source warnings do not summon the source warnings banner', () => {
    const section0 = makeSection(0, '1', 'Intro', 'A body.', 0);
    const analysis = makeAnalysis({
      source_sections: [section0],
      warnings: [
        'Citation validation dropped 1 of 3 findings on the first attempt.',
      ],
    });

    render(<Source analysis={analysis} onJumpToFinding={() => undefined} />);

    expect(screen.queryByTestId('source-warnings-banner')).toBeNull();
  });

  // -----------------------------------------------------------------
  // (e) CLICK + KEYBOARD JUMPS — onJumpToFinding called with the right index
  // -----------------------------------------------------------------
  it('click jumps: clicking the highlight + pressing Enter both call onJumpToFinding(index)', async () => {
    const section0 = makeSection(0, '4.2', 'Limit', 'Quote here.', 0);
    const findings: Finding[] = [
      makeFinding({
        severity: 'high',
        title: 'A',
        quote: 'Quote',
        source_offset: { section_index: 0, start: 0, end: 5 },
      }),
    ];
    const analysis = makeAnalysis({
      findings,
      source_sections: [section0],
    });

    const onJump = vi.fn();
    render(<Source analysis={analysis} onJumpToFinding={onJump} />);

    const highlight = screen.getByTestId('source-highlight');
    await userEvent.click(highlight);
    expect(onJump).toHaveBeenCalledWith(0);
    expect(onJump).toHaveBeenCalledTimes(1);

    // Tab into the highlight, press Enter.
    highlight.focus();
    await userEvent.keyboard('{Enter}');
    expect(onJump).toHaveBeenCalledTimes(2);
    expect(onJump).toHaveBeenLastCalledWith(0);
  });

  // -----------------------------------------------------------------
  // (f) ROLE + ARIA — every highlight is keyboard reachable
  // -----------------------------------------------------------------
  it('role + aria: every highlight is a button, tabIndex=0, and aria-label names the finding', () => {
    const section0 = makeSection(0, '4.2', 'Limit', 'Quote here.', 0);
    const findings: Finding[] = [
      makeFinding({
        severity: 'high',
        title: 'Liability cap dangerously low',
        quote: 'Quote',
        source_offset: { section_index: 0, start: 0, end: 5 },
      }),
    ];
    const analysis = makeAnalysis({
      findings,
      source_sections: [section0],
    });

    render(<Source analysis={analysis} onJumpToFinding={() => undefined} />);

    const highlight = screen.getByTestId('source-highlight');
    expect(highlight).toHaveAttribute('role', 'button');
    expect(highlight).toHaveAttribute('tabindex', '0');
    expect(highlight).toHaveAttribute(
      'aria-label',
      expect.stringContaining('Liability cap dangerously low'),
    );
  });

  // -----------------------------------------------------------------
  // (h) FIXUP-3 — overlap drops surface a Constitution VI banner
  // -----------------------------------------------------------------
  it('overlap banner: two findings whose offsets overlap surface a count banner above the source-doc', () => {
    // One section. Two findings whose offsets overlap: first occupies
    // [0, 10), second tries to start at 5 (inside the first highlight).
    // The renderer drops the second silently — fixup-3 surfaces the count.
    const section0 = makeSection(
      0,
      '4.2',
      'Limitation of Liability',
      'AAAAAAAAAA more text after the overlap zone here.',
      0,
    );
    const findings: Finding[] = [
      makeFinding({
        severity: 'high',
        title: 'First clause',
        quote: 'AAAAAAAAAA',
        source_offset: { section_index: 0, start: 0, end: 10 },
      }),
      makeFinding({
        severity: 'medium',
        title: 'Overlapping clause',
        quote: 'AAAAA',
        source_offset: { section_index: 0, start: 5, end: 10 },
      }),
    ];
    const analysis = makeAnalysis({
      findings,
      source_sections: [section0],
    });

    render(<Source analysis={analysis} onJumpToFinding={() => undefined} />);

    // Banner is rendered with the count and the Findings-tab pointer.
    const banner = screen.getByTestId('source-overlap-banner');
    expect(banner).toBeInTheDocument();
    expect(banner).toHaveTextContent(/^.*1 finding.*overlap.*Findings tab.*/i);

    // Only one highlight rendered (the first); the second was dropped.
    const highlights = screen.getAllByTestId('source-highlight');
    expect(highlights).toHaveLength(1);
    expect(highlights[0]!).toHaveAttribute('data-finding-index', '0');

    // Banner appears BEFORE the source-doc block.
    const sourceDoc = screen.getByTestId('source-doc');
    const followingMask = Node.DOCUMENT_POSITION_FOLLOWING;
    expect(
      // eslint-disable-next-line no-bitwise
      banner.compareDocumentPosition(sourceDoc) & followingMask,
    ).toBeTruthy();
  });

  it('overlap banner hidden when there are no overlapping highlights', () => {
    const section0 = makeSection(0, '4.2', 'Limit', 'Quote here.', 0);
    const findings: Finding[] = [
      makeFinding({
        severity: 'high',
        title: 'A',
        quote: 'Quote',
        source_offset: { section_index: 0, start: 0, end: 5 },
      }),
    ];
    const analysis = makeAnalysis({
      findings,
      source_sections: [section0],
    });

    render(<Source analysis={analysis} onJumpToFinding={() => undefined} />);

    expect(screen.queryByTestId('source-overlap-banner')).toBeNull();
  });

  // -----------------------------------------------------------------
  // (g) DOCUMENT ORDER PRESERVED — multiple highlights in one section
  // -----------------------------------------------------------------
  it('document order preserved: when section 0 has two findings, the earlier offset highlight appears first in the DOM', () => {
    // Section body: 0123456789 ABCDEFGHIJ KLMNOPQRST UVWXYZ — pick two non-overlapping ranges.
    const body =
      'aaaaaaaaaaQUOTE_ONE_HEREbbbbbbbbbbbbbbbQUOTE_TWO_HEREcccccccc';
    // QUOTE_ONE_HERE starts at index 10 (length 14)
    // QUOTE_TWO_HERE starts at index 39 (length 14)
    const section0 = makeSection(0, '1', 'Mixed', body, 0);

    const findings: Finding[] = [
      // First in array, but later in body — sorting by offset must put it second.
      makeFinding({
        severity: 'high',
        title: 'TWO',
        quote: 'QUOTE_TWO_HERE',
        source_offset: { section_index: 0, start: 39, end: 53 },
      }),
      makeFinding({
        severity: 'high',
        title: 'ONE',
        quote: 'QUOTE_ONE_HERE',
        source_offset: { section_index: 0, start: 10, end: 24 },
      }),
    ];

    const analysis = makeAnalysis({
      findings,
      source_sections: [section0],
    });

    render(<Source analysis={analysis} onJumpToFinding={() => undefined} />);

    const highlights = screen.getAllByTestId('source-highlight');
    expect(highlights).toHaveLength(2);
    // The "ONE" finding (offset 10) appears in DOM before "TWO" (offset 39),
    // even though "TWO" comes first in the findings array. data-finding-index
    // preserves the ORIGINAL findings index so cross-tab linking still works.
    expect(highlights[0]!).toHaveAttribute('data-finding-index', '1');
    expect(highlights[0]!).toHaveTextContent('QUOTE_ONE_HERE');
    expect(highlights[1]!).toHaveAttribute('data-finding-index', '0');
    expect(highlights[1]!).toHaveTextContent('QUOTE_TWO_HERE');
  });
});
