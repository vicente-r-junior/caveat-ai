/**
 * Findings tab — the centerpiece of Sprint 2.
 *
 * Order of concerns matches the prototype `findings-wrap`:
 *
 *   1. Pane header (eyebrow + serif title with N + lead copy).
 *   2. Warnings banner (Constitution VI — verbatim, ABOVE summary cards).
 *   3. Summary cards (high / medium / missing / elapsed).
 *   4. Filter chips.
 *   5. Empty state (one of two honest variants) OR finding cards.
 *
 * Finding state is React-only this sprint: a Map keyed on the original
 * index tracks pending / accepted / dismissed. Sprint 4 owns persistence
 * via the findings router; we deliberately keep this ephemeral so the
 * shape of the eventual API stays optional.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import type { AnalyzeResponse, Finding, Severity } from '../api/analyze';

type FindingState = 'pending' | 'accepted' | 'dismissed';
type FilterKey = 'all' | 'high' | 'missing' | 'accepted';

const NUMBER_WORDS: Record<number, string> = {
  1: 'One',
  2: 'Two',
  3: 'Three',
  4: 'Four',
  5: 'Five',
  6: 'Six',
  7: 'Seven',
  8: 'Eight',
  9: 'Nine',
  10: 'Ten',
  11: 'Eleven',
  12: 'Twelve',
};

const SEVERITY_BADGE: Record<Severity, string> = {
  high: 'bg-danger text-white',
  medium: 'bg-warn text-white',
  low: 'bg-gold text-white',
  missing: 'bg-ink text-white',
};

const SEVERITY_LABEL: Record<Severity, string> = {
  high: 'High',
  medium: 'Medium',
  low: 'Low',
  missing: 'Missing',
};

function pluralizeCount(n: number): string {
  const word = NUMBER_WORDS[n];
  const noun = n === 1 ? 'thing' : 'things';
  return `${word ?? n} ${noun}`;
}

type FindingsProps = {
  analysis: AnalyzeResponse;
  /**
   * Sprint 3 cross-tab linking. When set, the matching finding card is
   * scrolled into view and tagged with `data-finding-target="true"` for
   * 1500ms. Both props default to undefined; absent both, behavior is
   * byte-identical to Sprint 2.
   */
  targetFindingIndex?: number | null;
  onTargetHandled?: () => void;
};

export function Findings({
  analysis,
  targetFindingIndex,
  onTargetHandled,
}: FindingsProps): JSX.Element {
  const findings = analysis.findings;
  // Map keyed on the ORIGINAL findings index so cross-tab linking matches
  // the source_offset.section_index → finding-index mapping. Filter-reduced
  // index would not survive dismiss/filter operations.
  const cardRefs = useRef<Map<number, HTMLElement | null>>(new Map());

  // Cross-tab scroll: when the prop becomes a real index, look up the card
  // by original index, scroll it into view, tag it briefly, and clear.
  //
  // Note on the lifecycle: we deliberately do NOT clear the timeout in a
  // cleanup function, because `onTargetHandled?.()` synchronously sets the
  // parent's `targetFindingIndex` back to null, which retriggers this
  // effect with a null value. If that retrigger cleared the timer, the
  // attribute would never auto-clear. Fire-and-forget is fine: the
  // attribute lives on a DOM node ref'd by the live component, and the
  // 1500ms removal is best-effort visual decay.
  useEffect(() => {
    if (targetFindingIndex == null) return;
    const el = cardRefs.current.get(targetFindingIndex);
    if (!el) {
      // Card may be filtered out (e.g., dismissed). Still clear so we don't
      // leak the target index if the user re-applies filters later.
      onTargetHandled?.();
      return;
    }
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.setAttribute('data-finding-target', 'true');
    setTimeout(() => {
      el.removeAttribute('data-finding-target');
    }, 1500);
    onTargetHandled?.();
  }, [targetFindingIndex, onTargetHandled]);

  // index → state. Default 'pending'. Map-backed so dismiss is just a delete.
  const [stateById, setStateById] = useState<Map<number, FindingState>>(
    () => new Map(),
  );
  const [activeFilter, setActiveFilter] = useState<FilterKey>('all');

  const getState = (idx: number): FindingState =>
    stateById.get(idx) ?? 'pending';

  const setStateFor = (idx: number, next: FindingState): void => {
    setStateById((prev) => {
      const copy = new Map(prev);
      if (next === 'pending') {
        copy.delete(idx);
      } else {
        copy.set(idx, next);
      }
      return copy;
    });
  };

  // "kept" = everything not dismissed. Filter chips operate on this set.
  const keptIndices = useMemo<number[]>(
    () =>
      findings
        .map((_, i) => i)
        .filter((i) => getState(i) !== 'dismissed'),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [findings, stateById],
  );

  const acceptedCount = useMemo(
    () => keptIndices.filter((i) => getState(i) === 'accepted').length,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [keptIndices, stateById],
  );

  const filteredIndices = useMemo<number[]>(() => {
    switch (activeFilter) {
      case 'high':
        return keptIndices.filter((i) => findings[i]!.severity === 'high');
      case 'missing':
        return keptIndices.filter((i) => findings[i]!.severity === 'missing');
      case 'accepted':
        return keptIndices.filter((i) => getState(i) === 'accepted');
      default:
        return keptIndices;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFilter, keptIndices, findings, stateById]);

  const totalKept = keptIndices.length;
  const titleCount = totalKept;

  // Summary card counts — operate on the original findings list (pre-filter,
  // pre-dismiss) so the lawyer sees the model's actual output, not a UI view.
  const highCount = findings.filter((f) => f.severity === 'high').length;
  const medCount = findings.filter((f) => f.severity === 'medium').length;
  const missingCount = findings.filter((f) => f.severity === 'missing').length;

  const showFilters = findings.length > 0;
  const hasWarnings = analysis.warnings.length > 0;

  return (
    <div
      className="max-w-[880px] mx-auto px-8 py-8 pb-20"
      data-testid="findings-wrap"
    >
      {/* Pane header */}
      <div className="mb-8">
        <div className="font-mono text-[10px] text-burgundy uppercase tracking-[0.18em] mb-2.5">
          Tab 01 · technical analysis
        </div>
        <h1 className="font-serif text-4xl font-semibold leading-tight tracking-[-0.02em] mb-2">
          {titleCount > 0 ? (
            <>
              {pluralizeCount(titleCount)}{' '}
              <em className="italic font-normal text-burgundy">
                worth knowing.
              </em>
            </>
          ) : (
            'Findings'
          )}
        </h1>
        {titleCount > 0 ? (
          <p className="text-base text-ink-soft max-w-[600px] leading-relaxed">
            Each finding cites exact language from the contract. Click
            &ldquo;Accept&rdquo; to add a redline to your export package, or
            open Chat to dig into any of them.
          </p>
        ) : null}
      </div>

      {/* WARNINGS banner — verbatim, above summary cards (Constitution VI) */}
      {hasWarnings ? (
        <section
          data-testid="warnings-banner"
          className="border-l-[3px] border-burgundy bg-burgundy-soft rounded-r-md p-4 mb-6"
        >
          <p className="font-mono text-[10px] tracking-[0.18em] uppercase text-burgundy font-semibold mb-2">
            Warnings · model honesty
          </p>
          <ul className="space-y-2 list-none p-0">
            {analysis.warnings.map((w, i) => (
              <li
                key={i}
                className="text-sm leading-relaxed text-ink-soft"
                data-testid="warning-item"
              >
                {w}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* Findings summary — always rendered so the lawyer can see the model
          shipped 0 of everything when it did. */}
      <div
        className="grid grid-cols-2 lg:grid-cols-4 gap-px bg-line border border-line rounded-lg overflow-hidden mb-8"
        data-testid="findings-summary"
      >
        <SummaryCell label="High risk" value={String(highCount)} tone="danger" />
        <SummaryCell label="Medium" value={String(medCount)} tone="warn" />
        <SummaryCell label="Missing clauses" value={String(missingCount)} />
        <SummaryCell
          label="Analysis time"
          value={`${analysis.elapsed_seconds.toFixed(1)}s`}
        />
      </div>

      {/* Filter chips — only when there's something to filter */}
      {showFilters ? (
        <div
          className="flex gap-2 mb-5 items-center flex-wrap"
          data-testid="filter-chips"
        >
          <span className="font-mono text-[10px] tracking-[0.12em] uppercase text-ink-muted mr-1">
            Show
          </span>
          <FilterChip
            active={activeFilter === 'all'}
            onClick={() => setActiveFilter('all')}
          >
            All {totalKept}
          </FilterChip>
          <FilterChip
            active={activeFilter === 'high'}
            onClick={() => setActiveFilter('high')}
          >
            High only
          </FilterChip>
          <FilterChip
            active={activeFilter === 'missing'}
            onClick={() => setActiveFilter('missing')}
          >
            Missing
          </FilterChip>
          <FilterChip
            active={activeFilter === 'accepted'}
            onClick={() => setActiveFilter('accepted')}
          >
            Accepted ({acceptedCount})
          </FilterChip>
        </div>
      ) : null}

      {/* Empty states — honest, never "no risks found" */}
      {findings.length === 0 ? (
        hasWarnings ? (
          <div
            data-testid="findings-empty-with-warnings"
            className="font-serif italic text-base text-ink-soft p-6 bg-bg-soft border border-line rounded-lg leading-relaxed"
          >
            Analysis incomplete — see warnings above. The model may be
            undersized for this contract; consider re-running with{' '}
            <code className="font-mono not-italic text-[13px] text-ink">
              gemma4:31b-instruct-q4_K_M
            </code>{' '}
            on capable hardware.
          </div>
        ) : (
          <div
            data-testid="findings-empty-clean"
            className="font-serif italic text-base text-ink-soft p-6 bg-bg-soft border border-line rounded-lg leading-relaxed"
          >
            No findings produced. The contract appears clean against the
            loaded playbook, but please review manually before accepting
            this result.
          </div>
        )
      ) : (
        <div data-testid="finding-list">
          {filteredIndices.map((idx) => {
            const finding = findings[idx]!;
            const state = getState(idx);
            return (
              <FindingCard
                key={idx}
                finding={finding}
                state={state}
                onAccept={() =>
                  setStateFor(idx, state === 'accepted' ? 'pending' : 'accepted')
                }
                onDismiss={() => setStateFor(idx, 'dismissed')}
                cardRef={(el) => {
                  if (el) {
                    cardRefs.current.set(idx, el);
                  } else {
                    cardRefs.current.delete(idx);
                  }
                }}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}

type SummaryCellProps = {
  label: string;
  value: string;
  tone?: 'danger' | 'warn';
};

function SummaryCell({ label, value, tone }: SummaryCellProps): JSX.Element {
  const valueColor =
    tone === 'danger' ? 'text-danger' : tone === 'warn' ? 'text-warn' : 'text-ink';
  return (
    <div className="bg-bg p-4">
      <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-ink-muted mb-1.5">
        {label}
      </div>
      <div
        className={`font-serif text-3xl font-semibold leading-none ${valueColor}`}
      >
        {value}
      </div>
    </div>
  );
}

type FilterChipProps = {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
};

function FilterChip({ active, onClick, children }: FilterChipProps): JSX.Element {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'font-sans text-xs px-3 py-1.5 rounded-full border cursor-pointer font-medium transition-colors',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-burgundy focus-visible:ring-offset-2',
        active
          ? 'bg-ink text-white border-ink'
          : 'bg-bg-soft text-ink-soft border-line hover:border-ink-muted',
      ].join(' ')}
    >
      {children}
    </button>
  );
}

type FindingCardProps = {
  finding: Finding;
  state: FindingState;
  onAccept: () => void;
  onDismiss: () => void;
  /** Optional ref binder for cross-tab scroll (Sprint 3). */
  cardRef?: (el: HTMLElement | null) => void;
};

function FindingCard({
  finding,
  state,
  onAccept,
  onDismiss,
  cardRef,
}: FindingCardProps): JSX.Element {
  const isAccepted = state === 'accepted';
  const cardClass = [
    'bg-bg border rounded-lg mb-4 overflow-hidden transition-colors',
    isAccepted ? 'border-safe' : 'border-line hover:border-ink-muted',
  ].join(' ');

  return (
    <article
      ref={cardRef}
      className={cardClass}
      data-testid="finding-card"
      data-state={state}
    >
      <header className="p-4 px-5 flex items-center gap-3 border-b border-line-soft">
        <span
          className={[
            'font-mono text-[9px] font-bold uppercase tracking-[0.12em] px-2 py-1 rounded-sm shrink-0',
            SEVERITY_BADGE[finding.severity],
          ].join(' ')}
          data-testid="severity-badge"
          data-severity={finding.severity}
        >
          {SEVERITY_LABEL[finding.severity]}
        </span>
        <h3 className="font-serif text-lg font-semibold flex-1 leading-tight text-ink">
          {finding.title}
        </h3>
      </header>
      <div className="p-5">
        <blockquote
          className="border-l-[3px] border-burgundy pl-4 pr-4 py-3 mb-4 bg-burgundy-soft font-serif italic text-sm leading-relaxed text-ink-soft rounded-r-md"
          data-testid="finding-quote"
        >
          {finding.quote}
        </blockquote>
        <p
          className="text-sm leading-relaxed text-ink-soft mb-4"
          data-testid="finding-explain"
        >
          {finding.explanation}
        </p>
        {finding.redline.trim() !== '' ? (
          <div
            className="bg-bg-soft p-3.5 rounded-md border border-line"
            data-testid="finding-redline"
          >
            <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-burgundy font-semibold mb-2">
              ↳ Suggested redline
            </div>
            <div className="font-serif text-sm leading-relaxed text-ink">
              {finding.redline}
            </div>
          </div>
        ) : null}
        <div className="flex gap-2 mt-4 pt-4 border-t border-line-soft flex-wrap">
          <ActionButton
            variant={isAccepted ? 'accepted' : 'accept'}
            onClick={onAccept}
            testId="finding-accept"
          >
            {isAccepted ? '✓ Accepted' : '✓ Accept'}
          </ActionButton>
          <ActionButton
            variant="disabled"
            disabled
            title="Inline editing arrives in Sprint 4"
            testId="finding-edit"
          >
            Edit
          </ActionButton>
          <ActionButton
            variant="disabled"
            disabled
            title="Cross-document chat arrives in Sprint 4"
            testId="finding-ask"
          >
            Ask in chat
          </ActionButton>
          <ActionButton
            variant="dismiss"
            onClick={onDismiss}
            testId="finding-dismiss"
          >
            ✕ Dismiss
          </ActionButton>
        </div>
      </div>
    </article>
  );
}

type ActionVariant = 'accept' | 'accepted' | 'dismiss' | 'disabled';

type ActionButtonProps = {
  variant: ActionVariant;
  onClick?: () => void;
  disabled?: boolean;
  title?: string;
  testId?: string;
  children: React.ReactNode;
};

function ActionButton({
  variant,
  onClick,
  disabled,
  title,
  testId,
  children,
}: ActionButtonProps): JSX.Element {
  const base =
    'font-sans text-xs font-medium px-3 py-1.5 border rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-burgundy focus-visible:ring-offset-2';
  const variantClass: Record<ActionVariant, string> = {
    accept:
      'border-line bg-bg text-ink-soft cursor-pointer hover:text-safe hover:border-safe hover:bg-safe-soft',
    accepted:
      'border-safe bg-safe-soft text-safe cursor-pointer',
    dismiss:
      'border-line bg-bg text-ink-soft cursor-pointer hover:text-danger hover:border-danger hover:bg-danger-soft',
    disabled:
      'border-line bg-bg text-ink-muted opacity-60 cursor-not-allowed',
  };
  return (
    <button
      type="button"
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      title={title}
      data-testid={testId}
      className={[base, variantClass[variant]].join(' ')}
    >
      {children}
    </button>
  );
}

export default Findings;
