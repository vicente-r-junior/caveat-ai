/**
 * Client summary tab tests — Sprint 3 / US2.
 *
 * THE most important Sprint 3 test file: pins Constitution IV in the
 * summary surface. The summary disclaimer block is a structural
 * non-removable element with `data-testid="summary-disclaimer"`. Any DOM
 * tampering attempt is reconciled away on the next React render.
 *
 * Also pins Constitution V (every memo field is editable, the disclaimer is
 * not) and Constitution VI (when the model returns the canonical fallback
 * strings the four sections still render — never collapsed or hidden — so
 * the lawyer can SEE the model fell back).
 *
 * The component is pure on props.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ClientSummary } from './ClientSummary';
import type { AnalyzeResponse, ClientSummary as ClientSummaryT } from '../api/analyze';

function makeAnalysis(
  summary: Partial<ClientSummaryT> = {},
  overrides: Partial<AnalyzeResponse> = {},
): AnalyzeResponse {
  return {
    document_id: 'abc',
    contract_type: 'Acme Master Services Agreement',
    findings: [],
    client_summary: {
      what_this_contract_is:
        'This is a Master Services Agreement that governs your ongoing relationship with Acme.',
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
      ...summary,
    },
    warnings: [],
    elapsed_seconds: 1.5,
    source_sections: [],
    ...overrides,
  };
}

describe('<ClientSummary />', () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  // -----------------------------------------------------------------
  // (a) HAPPY PATH — every prototype field renders
  // -----------------------------------------------------------------
  it('happy path: renders pane title, letterhead, four sections, verdict, and disclaimer verbatim', () => {
    const analysis = makeAnalysis();
    render(<ClientSummary analysis={analysis} />);

    // Serif title with the prototype's "actually reads." copy.
    expect(screen.getByText(/actually reads\./i)).toBeInTheDocument();

    // Firm letterhead block visible.
    expect(screen.getByText(/Carter & Voss LLP · Memo/i)).toBeInTheDocument();
    expect(
      screen.getByText(/Re: Acme Master Services Agreement/i),
    ).toBeInTheDocument();

    // Four section blocks render verbatim content.
    expect(
      screen.getByRole('heading', { level: 3, name: 'What this contract is' }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/governs your ongoing relationship with Acme/i),
    ).toBeInTheDocument();

    expect(
      screen.getByRole('heading', {
        level: 3,
        name: "What you're committing to",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Pay Acme on time, in advance/i),
    ).toBeInTheDocument();

    expect(
      screen.getByRole('heading', { level: 3, name: 'The biggest risks' }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole('heading', { level: 3, name: 'Recommendation' }),
    ).toBeInTheDocument();
    // Verdict box renders the recommendation prose.
    expect(
      screen.getByText(/Do not sign as-is\. Negotiate the three items above/i),
    ).toBeInTheDocument();

    // Summary disclaimer carries data-testid AND its full text matches the prop.
    const disclaimer = screen.getByTestId('summary-disclaimer');
    expect(disclaimer).toBeInTheDocument();
    expect(disclaimer).toHaveTextContent(
      analysis.client_summary.disclaimer,
    );
  });

  // -----------------------------------------------------------------
  // (b) DISCLAIMER IS NON-REMOVABLE — Constitution IV at component level
  // -----------------------------------------------------------------
  it('disclaimer is non-removable: removing the node from the DOM and forcing a re-render brings it back', async () => {
    function Wrapper(): JSX.Element {
      const [n, setN] = useState(0);
      const analysis = makeAnalysis(undefined, { contract_type: `MSA #${n}` });
      return (
        <>
          <button
            type="button"
            data-testid="bump"
            onClick={() => setN((x) => x + 1)}
          >
            bump
          </button>
          <ClientSummary analysis={analysis} />
        </>
      );
    }

    render(<Wrapper />);

    const original = screen.getByTestId('summary-disclaimer');
    expect(original).toBeInTheDocument();

    // Tamper: remove the node from the DOM directly.
    original.remove();
    expect(screen.queryByTestId('summary-disclaimer')).toBeNull();

    // Force a re-render via a parent prop change.
    await userEvent.click(screen.getByTestId('bump'));

    // React reconciles it back. Constitution IV pinned.
    expect(screen.getByTestId('summary-disclaimer')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------
  // (c) EDIT-IN-PLACE — Save persists in local state, prop unmodified
  // -----------------------------------------------------------------
  it('edit-in-place: clicking Edit on "What this contract is" → textarea → Save → rendered text reflects edit', async () => {
    const analysis = makeAnalysis();
    const original = analysis.client_summary.what_this_contract_is;

    // Snapshot the prop to assert non-mutation later.
    const snapshot = { ...analysis.client_summary };

    render(<ClientSummary analysis={analysis} />);

    // Original prose visible.
    expect(screen.getByText(original)).toBeInTheDocument();

    // Click the Edit button on the first section.
    const editBtn = screen.getByTestId('edit-what_this_contract_is');
    await userEvent.click(editBtn);

    // Textarea appears prefilled with the original value.
    const textarea = screen.getByTestId(
      'textarea-what_this_contract_is',
    ) as HTMLTextAreaElement;
    expect(textarea).toBeInTheDocument();
    expect(textarea.value).toBe(original);

    // Type a replacement.
    await userEvent.clear(textarea);
    await userEvent.type(textarea, 'EDITED — a tighter sentence.');

    // Save.
    await userEvent.click(screen.getByTestId('save-what_this_contract_is'));

    // Rendered <p> reflects the edit; textarea is gone.
    expect(screen.getByText('EDITED — a tighter sentence.')).toBeInTheDocument();
    expect(
      screen.queryByTestId('textarea-what_this_contract_is'),
    ).toBeNull();

    // The prop object was not mutated — edits live in local state only.
    expect(analysis.client_summary).toEqual(snapshot);
  });

  // -----------------------------------------------------------------
  // (d) EDIT-THEN-CANCEL — original prop value restored
  // -----------------------------------------------------------------
  it('edit-then-cancel: clicking Cancel after typing reverts to the original prop value', async () => {
    const analysis = makeAnalysis();
    const original = analysis.client_summary.what_this_contract_is;

    render(<ClientSummary analysis={analysis} />);

    await userEvent.click(screen.getByTestId('edit-what_this_contract_is'));
    const textarea = screen.getByTestId(
      'textarea-what_this_contract_is',
    ) as HTMLTextAreaElement;
    await userEvent.clear(textarea);
    await userEvent.type(textarea, 'should not stick');

    await userEvent.click(screen.getByTestId('cancel-what_this_contract_is'));

    // Textarea gone, original prose back.
    expect(
      screen.queryByTestId('textarea-what_this_contract_is'),
    ).toBeNull();
    expect(screen.getByText(original)).toBeInTheDocument();
    expect(screen.queryByText('should not stick')).toBeNull();
  });

  // -----------------------------------------------------------------
  // (e) NO EDIT BUTTON ON DISCLAIMER — Constitution IV / V boundary
  // -----------------------------------------------------------------
  it('no Edit affordance on the disclaimer — it is structural, not editorial', () => {
    const analysis = makeAnalysis();
    render(<ClientSummary analysis={analysis} />);

    // Sanity: the four field-level Edit buttons exist.
    expect(
      screen.getByTestId('edit-what_this_contract_is'),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId('edit-what_youre_committing_to'),
    ).toBeInTheDocument();
    expect(screen.getByTestId('edit-biggest_risks')).toBeInTheDocument();
    expect(screen.getByTestId('edit-recommendation')).toBeInTheDocument();

    // Disclaimer-level Edit button does NOT exist.
    expect(screen.queryByTestId('edit-disclaimer')).toBeNull();

    // Belt: the disclaimer node has no descendant <button>.
    const disclaimer = screen.getByTestId('summary-disclaimer');
    expect(disclaimer.querySelector('button')).toBeNull();
  });

  // -----------------------------------------------------------------
  // (f) BIGGEST RISKS RENDER AS <ul> — one <li> per entry verbatim
  // -----------------------------------------------------------------
  it('biggest_risks renders as <ul> with one <li> per entry verbatim', () => {
    const analysis = makeAnalysis({
      biggest_risks: ['First risk', 'Second risk', 'Third risk'],
    });
    render(<ClientSummary analysis={analysis} />);

    const list = screen.getByTestId('biggest-risks-list');
    expect(list.tagName).toBe('UL');
    const items = list.querySelectorAll('li');
    expect(items).toHaveLength(3);
    expect(items[0]!).toHaveTextContent('First risk');
    expect(items[1]!).toHaveTextContent('Second risk');
    expect(items[2]!).toHaveTextContent('Third risk');
  });

  // -----------------------------------------------------------------
  // (h) FIXUP-2 — ephemerality eyebrow is always visible
  // -----------------------------------------------------------------
  it('ephemerality eyebrow is always visible alongside the edit affordances', () => {
    const analysis = makeAnalysis();
    render(<ClientSummary analysis={analysis} />);

    const eyebrow = screen.getByTestId('ephemerality-eyebrow');
    expect(eyebrow).toBeInTheDocument();
    // The text names the session-local boundary explicitly so a lawyer
    // reading the screen knows their edits will not survive a refresh.
    expect(eyebrow).toHaveTextContent(/session-local/i);
    expect(eyebrow).toHaveTextContent(/Sprint 5/i);
    // Burgundy mono treatment — Constitution VI eyebrow pattern.
    expect(eyebrow.className).toContain('text-burgundy');
    expect(eyebrow.className).toContain('font-mono');
  });

  // -----------------------------------------------------------------
  // (i) FIXUP-2 — beforeunload handler attaches only when edits exist
  // -----------------------------------------------------------------
  it('beforeunload handler is attached only after at least one Save (and detached on unmount)', async () => {
    const addSpy = vi.spyOn(window, 'addEventListener');
    const removeSpy = vi.spyOn(window, 'removeEventListener');

    const analysis = makeAnalysis();
    const { unmount } = render(<ClientSummary analysis={analysis} />);

    // No beforeunload listener attached on a clean render — the user has
    // not edited anything, so refreshing should not pop a dialog.
    expect(
      addSpy.mock.calls.some(([evt]) => evt === 'beforeunload'),
    ).toBe(false);

    // Edit and Save: now the component holds an uncommitted edit and the
    // handler should be installed.
    await userEvent.click(screen.getByTestId('edit-what_this_contract_is'));
    const textarea = screen.getByTestId(
      'textarea-what_this_contract_is',
    ) as HTMLTextAreaElement;
    await userEvent.clear(textarea);
    await userEvent.type(textarea, 'edited prose');
    await userEvent.click(screen.getByTestId('save-what_this_contract_is'));

    expect(
      addSpy.mock.calls.some(([evt]) => evt === 'beforeunload'),
    ).toBe(true);

    // Unmount drops the listener.
    unmount();
    expect(
      removeSpy.mock.calls.some(([evt]) => evt === 'beforeunload'),
    ).toBe(true);

    addSpy.mockRestore();
    removeSpy.mockRestore();
  });

  // -----------------------------------------------------------------
  // (j) FIXUP-2 — saved (this session) inline feedback on Save
  // -----------------------------------------------------------------
  it('Save flashes "saved (this session)" inline next to the section heading', async () => {
    const analysis = makeAnalysis();
    render(<ClientSummary analysis={analysis} />);

    // No `saved-*` marker before any Save.
    expect(
      screen.queryByTestId('saved-what_this_contract_is'),
    ).toBeNull();

    await userEvent.click(screen.getByTestId('edit-what_this_contract_is'));
    const textarea = screen.getByTestId(
      'textarea-what_this_contract_is',
    ) as HTMLTextAreaElement;
    await userEvent.clear(textarea);
    await userEvent.type(textarea, 'edited');
    await userEvent.click(screen.getByTestId('save-what_this_contract_is'));

    // Immediately after Save: inline feedback is visible.
    const flash = screen.getByTestId('saved-what_this_contract_is');
    expect(flash).toBeInTheDocument();
    expect(flash).toHaveTextContent(/saved \(this session\)/i);

    // The feedback should not stick — wait for the auto-clear.
    await vi.waitFor(
      () => {
        expect(
          screen.queryByTestId('saved-what_this_contract_is'),
        ).toBeNull();
      },
      { timeout: 3000 },
    );
  });

  // -----------------------------------------------------------------
  // (g) HONEST EMPTY FALLBACK — fallback strings still render visibly
  // -----------------------------------------------------------------
  it('honest empty fallback: all four sections render even when fields are the canonical "(missing)" fallback', () => {
    const analysis = makeAnalysis({
      what_this_contract_is: '(missing)',
      what_youre_committing_to: '(missing)',
      biggest_risks: ['(missing)'],
      recommendation: '(missing)',
      disclaimer: 'AI-generated output — attorney review required.',
    });

    render(<ClientSummary analysis={analysis} />);

    // Headings still present.
    expect(
      screen.getByRole('heading', { level: 3, name: 'What this contract is' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', {
        level: 3,
        name: "What you're committing to",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 3, name: 'The biggest risks' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 3, name: 'Recommendation' }),
    ).toBeInTheDocument();

    // The fallback string is visible at least 4 times (one per section/list/verdict).
    expect(screen.getAllByText('(missing)').length).toBeGreaterThanOrEqual(4);

    // Disclaimer still renders.
    expect(screen.getByTestId('summary-disclaimer')).toBeInTheDocument();
  });
});
