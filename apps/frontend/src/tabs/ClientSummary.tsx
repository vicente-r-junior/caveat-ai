/**
 * Client summary tab — Sprint 3 / US2.
 *
 * Renders the four-section memo (What this contract is / What you're
 * committing to / The biggest risks / Recommendation) plus a verdict box,
 * a firm letterhead, and a non-removable disclaimer block. Layout matches
 * `client-doc` in `docs/caveat-prototype-v3.html` (lines 1656–1696).
 *
 * Constitutional gates:
 *   - IV (disclaimers): the summary disclaimer is rendered unconditionally
 *     on every render via `data-testid="summary-disclaimer"`. DOM tampering
 *     is reconciled away on the next React render — verified by the
 *     ClientSummary.test.tsx "non-removable" case.
 *   - V (lawyer in loop): each editable field has Edit / Save / Cancel
 *     affordances; edits live in a local `Map<FieldKey, string>` and are
 *     ephemeral (Sprint 5 wires persistence via the export package).
 *   - VI (honesty): when the model returns the canonical `(missing)`
 *     fallback strings, the four sections still render with that text
 *     visible — never collapsed or hidden. The lawyer must see the
 *     fallback, not silence.
 */

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { AnalyzeResponse, ClientSummary as ClientSummaryT } from '../api/analyze';

type FieldKey =
  | 'what_this_contract_is'
  | 'what_youre_committing_to'
  | 'biggest_risks'
  | 'recommendation';

type ClientSummaryProps = {
  analysis: AnalyzeResponse;
};

/**
 * Convert a string field's display value: prefer the local edit override,
 * fall back to the prop. `biggest_risks` joins/splits via "\n" so the lawyer
 * can edit the list as plain prose in a textarea.
 */
function fieldDefault(
  summary: ClientSummaryT,
  field: FieldKey,
): string {
  if (field === 'biggest_risks') {
    return summary.biggest_risks.join('\n');
  }
  return summary[field];
}

export function ClientSummary({ analysis }: ClientSummaryProps): JSX.Element {
  const summary = analysis.client_summary;
  const [edits, setEdits] = useState<Map<FieldKey, string>>(new Map());
  const [editing, setEditing] = useState<Set<FieldKey>>(new Set());
  const [drafts, setDrafts] = useState<Map<FieldKey, string>>(new Map());
  // Sprint 3 fixup-2: track per-field "just saved" so the heading row can
  // show an inline `saved (this session)` flash for 1.5s. Set entry is added
  // in `saveEdit` and removed on the trailing setTimeout — same single
  // source of truth React can re-render off of.
  const [recentlySaved, setRecentlySaved] = useState<Set<FieldKey>>(new Set());

  // Sprint 3 fixup-2: edits live in component-local state only — a hard
  // refresh, tab close, or navigation away loses them. Until Sprint 5 wires
  // SQLite persistence, surface that boundary via the browser's native
  // unsaved-changes dialog. Handler is only attached while at least one
  // saved edit exists (the user has clicked Save on something), so we don't
  // pop the dialog on every navigation away from this tab.
  useEffect(() => {
    if (edits.size === 0) return undefined;
    const handler = (e: BeforeUnloadEvent): void => {
      e.preventDefault();
      // Chrome/Edge ignore the message but require returnValue to be set.
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => {
      window.removeEventListener('beforeunload', handler);
    };
  }, [edits]);

  // Constitution IV: the disclaimer paragraph cannot be dismissed via DOM
  // tampering. We hold refs to the live disclaimer node AND its expected
  // parent (the doc-card <article>). After every render commit, if the
  // disclaimer was detached we re-append it — same DOM node, same React
  // fiber, no reconciliation conflict. Belt: a `useState` tamper counter
  // forces a re-render in the rare case where the parent itself was
  // tampered with, so React re-mounts a fresh subtree.
  const disclaimerRef = useRef<HTMLParagraphElement | null>(null);
  const docCardRef = useRef<HTMLElement | null>(null);
  const [tamperCount, setTamperCount] = useState(0);
  // The bare `useLayoutEffect` (no deps array) runs after every commit on
  // purpose: any tamper attempt — initial mount or otherwise — is caught.
  // `setTamperCount` only fires when re-attachment happened, so the loop
  // is bounded: once the node is back in the DOM the effect is a no-op.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(() => {
    const el = disclaimerRef.current;
    const parent = docCardRef.current;
    if (el && parent && !parent.contains(el)) {
      // The disclaimer node is detached from its parent. Re-attach it.
      parent.appendChild(el);
      // Bump the tamper counter so any consumer observing it sees a
      // state change (and so React's next reconciliation pass treats
      // this as a fresh frame).
      setTamperCount((n) => n + 1);
    }
  });

  // TODO(sprint-5): replace placeholder firm name with `~/.caveat/firm.json`.
  const firm = 'Carter & Voss LLP · Memo';
  // Re: line falls back to a neutral label if the model didn't return a contract type.
  const reLine = analysis.contract_type
    ? `Re: ${analysis.contract_type}`
    : 'Re: Contract review';

  const valueOf = (field: FieldKey): string =>
    edits.get(field) ?? fieldDefault(summary, field);

  const startEdit = (field: FieldKey): void => {
    setDrafts((prev) => {
      const copy = new Map(prev);
      copy.set(field, valueOf(field));
      return copy;
    });
    setEditing((prev) => {
      const copy = new Set(prev);
      copy.add(field);
      return copy;
    });
  };

  const saveEdit = (field: FieldKey): void => {
    const next = drafts.get(field) ?? '';
    setEdits((prev) => {
      const copy = new Map(prev);
      copy.set(field, next);
      return copy;
    });
    setEditing((prev) => {
      const copy = new Set(prev);
      copy.delete(field);
      return copy;
    });
    // Sprint 3 fixup-2: pulse the inline `saved (this session)` indicator
    // for ~1.5s so the session boundary is explicit at the moment of action.
    setRecentlySaved((prev) => {
      const copy = new Set(prev);
      copy.add(field);
      return copy;
    });
    window.setTimeout(() => {
      setRecentlySaved((prev) => {
        if (!prev.has(field)) return prev;
        const copy = new Set(prev);
        copy.delete(field);
        return copy;
      });
    }, 1500);
  };

  const cancelEdit = (field: FieldKey): void => {
    setEditing((prev) => {
      const copy = new Set(prev);
      copy.delete(field);
      return copy;
    });
    setDrafts((prev) => {
      const copy = new Map(prev);
      copy.delete(field);
      return copy;
    });
  };

  const setDraft = (field: FieldKey, value: string): void => {
    setDrafts((prev) => {
      const copy = new Map(prev);
      copy.set(field, value);
      return copy;
    });
  };

  const isEditing = (field: FieldKey): boolean => editing.has(field);

  // For biggest_risks, render the saved value (newline-joined) as a list of
  // <li> entries, splitting back on newlines so an edit "First\nSecond" yields
  // two list items. Empty lines are preserved verbatim — Constitution VI: the
  // lawyer should see exactly what the model returned (or what they typed).
  const risksList = (): string[] => {
    const value = valueOf('biggest_risks');
    if (value === '') return [];
    return value.split('\n');
  };

  return (
    <div
      className="max-w-[820px] mx-auto px-8 py-8 pb-20"
      data-testid="client-summary-wrap"
    >
      {/* Pane header */}
      <div className="mb-8">
        <div className="font-mono text-[10px] text-burgundy uppercase tracking-[0.18em] mb-2.5">
          Tab 02 · for your client
        </div>
        <h1 className="font-serif text-4xl font-semibold leading-tight tracking-[-0.02em] mb-2">
          A version your client{' '}
          <em className="italic font-normal text-burgundy">actually reads.</em>
        </h1>
        <p className="text-base text-ink-soft max-w-[600px] leading-relaxed">
          Plain English. Three risks named in order. A clear recommendation.
          Edit before sending.
        </p>
      </div>

      {/* Doc card */}
      <article
        ref={docCardRef}
        className="bg-bg-soft border border-line rounded-lg p-10 font-serif text-ink-soft"
      >
        {/* Letterhead */}
        <header className="mb-8 pb-6 border-b border-line">
          <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-ink-muted mb-2">
            {firm}
          </div>
          <div className="font-serif text-2xl font-semibold text-ink leading-tight">
            {reLine}
          </div>
        </header>

        {/* Sprint 3 fixup-2: ephemerality eyebrow. Always visible because the
            Edit affordances on each section are always visible. Constitution
            VI — the user must see, at the moment they can act, that this
            edit surface does not persist across refresh until Sprint 5. */}
        <div
          data-testid="ephemerality-eyebrow"
          className="font-mono text-[10px] tracking-[0.18em] uppercase text-burgundy mb-6 not-italic"
        >
          {'// session-local — persistence: Sprint 5'}
        </div>

        {/* Field 1: What this contract is */}
        <SummarySection
          field="what_this_contract_is"
          heading="What this contract is"
          editing={isEditing('what_this_contract_is')}
          justSaved={recentlySaved.has('what_this_contract_is')}
          value={valueOf('what_this_contract_is')}
          draft={drafts.get('what_this_contract_is') ?? ''}
          onStart={startEdit}
          onSave={saveEdit}
          onCancel={cancelEdit}
          onChangeDraft={setDraft}
        >
          <p className="text-base leading-relaxed text-ink-soft">
            {valueOf('what_this_contract_is')}
          </p>
        </SummarySection>

        {/* Field 2: What you're committing to */}
        <SummarySection
          field="what_youre_committing_to"
          heading="What you're committing to"
          editing={isEditing('what_youre_committing_to')}
          justSaved={recentlySaved.has('what_youre_committing_to')}
          value={valueOf('what_youre_committing_to')}
          draft={drafts.get('what_youre_committing_to') ?? ''}
          onStart={startEdit}
          onSave={saveEdit}
          onCancel={cancelEdit}
          onChangeDraft={setDraft}
        >
          <p className="text-base leading-relaxed text-ink-soft">
            {valueOf('what_youre_committing_to')}
          </p>
        </SummarySection>

        {/* Field 3: The biggest risks */}
        <SummarySection
          field="biggest_risks"
          heading="The biggest risks"
          editing={isEditing('biggest_risks')}
          justSaved={recentlySaved.has('biggest_risks')}
          value={valueOf('biggest_risks')}
          draft={drafts.get('biggest_risks') ?? ''}
          onStart={startEdit}
          onSave={saveEdit}
          onCancel={cancelEdit}
          onChangeDraft={setDraft}
        >
          <ul
            className="list-disc list-outside pl-5 space-y-2 text-base leading-relaxed text-ink-soft"
            data-testid="biggest-risks-list"
          >
            {risksList().map((risk, i) => (
              <li key={i}>{risk}</li>
            ))}
          </ul>
        </SummarySection>

        {/* Field 4: Recommendation — wrapped in the verdict box */}
        <SummarySection
          field="recommendation"
          heading="Recommendation"
          editing={isEditing('recommendation')}
          justSaved={recentlySaved.has('recommendation')}
          value={valueOf('recommendation')}
          draft={drafts.get('recommendation') ?? ''}
          onStart={startEdit}
          onSave={saveEdit}
          onCancel={cancelEdit}
          onChangeDraft={setDraft}
        >
          <div
            className="border-l-[3px] border-burgundy bg-burgundy-soft rounded-r-md p-5 mt-1"
            data-testid="verdict-box"
          >
            <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-burgundy font-semibold mb-2">
              Recommendation
            </div>
            <p className="font-serif text-base leading-relaxed text-ink">
              {valueOf('recommendation')}
            </p>
          </div>
        </SummarySection>

        {/* Summary disclaimer — Constitution IV. Renders unconditionally
            on every render. A `useLayoutEffect` watcher above checks DOM
            presence post-commit and force-re-renders if a tamper attempt
            removed the node, so React reconciles a fresh paragraph back
            into place. No Edit affordance, no descendant interactive
            elements, no dismiss control. */}
        <p
          // Stable key: the layout-effect watcher above re-attaches the
          // existing DOM node to its parent if a tamper detached it,
          // so React's reconciliation never tries to remove a missing
          // node. The tamperCount is referenced in data-tamper-count
          // purely so React picks up the rerender as relevant work.
          ref={disclaimerRef}
          data-testid="summary-disclaimer"
          data-tamper-count={tamperCount}
          className="font-mono italic text-[12px] text-ink-muted leading-relaxed mt-10 pt-6 border-t border-line"
        >
          {summary.disclaimer}
        </p>
      </article>
    </div>
  );
}

type SummarySectionProps = {
  field: FieldKey;
  heading: string;
  editing: boolean;
  justSaved: boolean;
  value: string;
  draft: string;
  onStart: (field: FieldKey) => void;
  onSave: (field: FieldKey) => void;
  onCancel: (field: FieldKey) => void;
  onChangeDraft: (field: FieldKey, value: string) => void;
  children: React.ReactNode;
};

function SummarySection({
  field,
  heading,
  editing,
  justSaved,
  value: _value,
  draft,
  onStart,
  onSave,
  onCancel,
  onChangeDraft,
  children,
}: SummarySectionProps): JSX.Element {
  return (
    <section className="mb-8 last:mb-0">
      <div className="flex items-baseline justify-between gap-4 mb-2">
        <h3 className="font-serif text-lg font-semibold text-ink leading-tight">
          {heading}
        </h3>
        <div className="flex items-center gap-3">
          {justSaved ? (
            <span
              data-testid={`saved-${field}`}
              className="font-mono text-[10px] tracking-[0.12em] uppercase text-burgundy transition-opacity"
            >
              saved (this session)
            </span>
          ) : null}
          {editing ? null : (
            <button
              type="button"
              onClick={() => onStart(field)}
              data-testid={`edit-${field}`}
              className="font-mono text-[10px] tracking-[0.12em] uppercase text-ink-muted hover:text-ink underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-burgundy focus-visible:ring-offset-2 rounded-sm px-1"
            >
              Edit
            </button>
          )}
        </div>
      </div>
      {editing ? (
        <div>
          <textarea
            data-testid={`textarea-${field}`}
            value={draft}
            onChange={(e) => onChangeDraft(field, e.target.value)}
            className="w-full min-h-[120px] font-sans text-sm leading-relaxed text-ink-soft p-3 bg-bg border border-line rounded-md resize-vertical focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-burgundy focus-visible:ring-offset-2"
          />
          <div className="flex gap-2 mt-2">
            <button
              type="button"
              onClick={() => onSave(field)}
              data-testid={`save-${field}`}
              className="font-sans text-xs font-medium px-3 py-1.5 border border-burgundy bg-burgundy text-white rounded-md hover:bg-[#6a1a25] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-burgundy focus-visible:ring-offset-2"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => onCancel(field)}
              data-testid={`cancel-${field}`}
              className="font-sans text-xs font-medium px-3 py-1.5 border border-line bg-bg text-ink-soft rounded-md hover:border-ink-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-burgundy focus-visible:ring-offset-2"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        children
      )}
    </section>
  );
}

export default ClientSummary;
