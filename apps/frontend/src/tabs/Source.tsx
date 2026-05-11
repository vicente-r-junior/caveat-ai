/**
 * Source tab — Sprint 3 / US2.
 *
 * Renders `analysis.source_sections` in document order. Findings whose
 * `source_offset` falls within a section's body emit a severity-tinted
 * `<button>` highlight at the exact slice; clicking (or pressing Enter on)
 * a highlight calls `onJumpToFinding(findingIndex)`, which the Review page
 * uses to flip back to the Findings tab and scroll the matching card.
 *
 * Constitutional gates:
 *   - III (no invention): a finding only renders a highlight when its
 *     `source_offset` resolves inside a section's body. There is no
 *     client-side fuzzy match — the offsets come from the backend's
 *     `map_finding_offsets` stage which uses the same exact-substring
 *     rule as the citation validator.
 *   - VI (honesty): when the backend's offset stage couldn't locate a
 *     finding's quote (`source_offset === null`), it appends a
 *     "Source viewer:" warning to `analysis.warnings`. This tab repeats
 *     those warnings inline above the source-doc — belt-and-suspenders
 *     with the Findings warnings banner so the lawyer who lands on
 *     Source first does not miss the honest miss.
 *   - NFR-005 (keyboard reach): every highlight is a real `<button>` with
 *     `tabIndex={0}`, `role="button"`, an `aria-label` naming the target
 *     finding, and Enter/Space activation.
 */

import { useMemo } from 'react';
import type {
  AnalyzeResponse,
  Finding,
  Severity,
  SourceOffset,
  SourceSection,
} from '../api/analyze';

const SEVERITY_HIGHLIGHT: Record<Severity, string> = {
  high: 'bg-danger-soft border-b-2 border-danger',
  medium: 'bg-danger-soft border-b-2 border-danger',
  low: 'bg-warn-soft border-b-2 border-warn',
  missing: 'bg-bg-tint border-b-2 border-ink-muted',
};

type SourceProps = {
  analysis: AnalyzeResponse;
  onJumpToFinding: (findingIndex: number) => void;
};

type AnchoredFinding = {
  /** Original index into `analysis.findings`. Crucial for cross-tab linking. */
  index: number;
  finding: Finding;
  offset: SourceOffset;
};

export function Source({ analysis, onJumpToFinding }: SourceProps): JSX.Element {
  const sections = analysis.source_sections;
  const findings = analysis.findings;

  // Findings with a real offset, indexed for cross-tab linking. We keep the
  // ORIGINAL index so clicking a highlight scrolls the right Findings card
  // even when offsets order ≠ findings order.
  const anchored = useMemo<AnchoredFinding[]>(() => {
    return findings
      .map((f, i) => ({ index: i, finding: f, offset: f.source_offset }))
      .filter((row): row is AnchoredFinding => row.offset !== null);
  }, [findings]);

  // Source-tab-scoped warnings (Constitution VI banner). The backend uses
  // the literal "Source viewer:" prefix when the offset stage misses; we
  // surface every warning carrying that token verbatim.
  const sourceWarnings = useMemo(
    () => analysis.warnings.filter((w) => w.includes('Source viewer:')),
    [analysis.warnings],
  );

  // Sprint 3 fixup-3: count findings that the render loop would drop because
  // their offset overlaps an earlier highlight in the same section. Mirrors
  // the skip logic in `renderBodyWithHighlights` exactly (the "localStart <
  // cursor" branch), but only counts — does not render. Constitution VI:
  // when this count is > 0 we surface a banner so the lawyer who reads
  // Source does not assume the rendered highlights are exhaustive. Overlap
  // merging itself is deferred to Sprint 4; the Findings tab remains
  // authoritative for the complete list.
  const overlapDroppedCount = useMemo<number>(() => {
    let dropped = 0;
    for (const section of sections) {
      const inSection = anchored
        .filter((row) => row.offset.section_index === section.idx)
        .sort((a, b) => a.offset.start - b.offset.start);
      const bodyStart = section.char_end - section.body.length;
      let cursor = 0;
      for (const row of inSection) {
        const localStart = row.offset.start - bodyStart;
        const localEnd = row.offset.end - bodyStart;
        // Out-of-range / empty highlights are not "overlap" drops — they
        // are malformed offsets, addressed by the Constitution VI warnings
        // emitted by the backend offset stage. Only count true overlaps:
        // the highlight whose start sits inside a previous highlight.
        if (localStart < 0 || localEnd > section.body.length || localEnd <= localStart) {
          continue;
        }
        if (localStart < cursor) {
          dropped += 1;
          continue;
        }
        cursor = localEnd;
      }
    }
    return dropped;
  }, [sections, anchored]);

  return (
    <div
      className="max-w-[920px] mx-auto px-8 py-8 pb-20"
      data-testid="source-wrap"
    >
      {/* Pane header */}
      <div className="mb-8">
        <div className="font-mono text-[10px] text-burgundy uppercase tracking-[0.18em] mb-2.5">
          Tab 03 · the original
        </div>
        <h1 className="font-serif text-4xl font-semibold leading-tight tracking-[-0.02em] mb-2">
          The contract,{' '}
          <em className="italic font-normal text-burgundy">annotated.</em>
        </h1>
        <p className="text-base text-ink-soft max-w-[600px] leading-relaxed">
          Risk passages are highlighted. Click any highlight to jump to its
          finding.
        </p>
      </div>

      {/* Constitution VI warnings banner — only when source-related warnings exist */}
      {sourceWarnings.length > 0 ? (
        <section
          data-testid="source-warnings-banner"
          className="border-l-[3px] border-burgundy bg-burgundy-soft rounded-r-md p-4 mb-6"
        >
          <p className="font-mono text-[10px] tracking-[0.18em] uppercase text-burgundy font-semibold mb-2">
            Warnings · model honesty
          </p>
          <ul className="space-y-2 list-none p-0">
            {sourceWarnings.map((w, i) => (
              <li
                key={i}
                className="text-sm leading-relaxed text-ink-soft"
                data-testid="source-warning-item"
              >
                {w}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {/* Sprint 3 fixup-3: surface overlap drops. Constitution VI — the
          Findings tab is authoritative, but the lawyer reading Source must
          know the rendered highlights are not exhaustive. Banner pattern
          matches the warnings banner above (burgundy-soft + left border). */}
      {overlapDroppedCount > 0 ? (
        <section
          data-testid="source-overlap-banner"
          className="border-l-[3px] border-burgundy bg-burgundy-soft rounded-r-md p-4 mb-6"
        >
          <p className="font-mono text-[10px] tracking-[0.18em] uppercase text-burgundy font-semibold mb-2">
            Warnings · source overlap
          </p>
          <p className="text-sm leading-relaxed text-ink-soft">
            {overlapDroppedCount} finding
            {overlapDroppedCount === 1 ? '' : 's'} couldn&rsquo;t be
            highlighted in Source due to overlap — see the Findings tab for
            the complete list.
          </p>
        </section>
      ) : null}

      {/* Source-doc block */}
      <article
        className="bg-bg-soft border border-line rounded-lg max-w-[800px] mx-auto"
        style={{ padding: '40px 48px' }}
        data-testid="source-doc"
      >
        {sections.map((section) => (
          <SourceSectionView
            key={section.idx}
            section={section}
            anchored={anchored}
            onJump={onJumpToFinding}
          />
        ))}
      </article>
    </div>
  );
}

type SourceSectionViewProps = {
  section: SourceSection;
  anchored: AnchoredFinding[];
  onJump: (findingIndex: number) => void;
};

function SourceSectionView({
  section,
  anchored,
  onJump,
}: SourceSectionViewProps): JSX.Element {
  // Findings whose offset belongs to THIS section. Sort by absolute start
  // offset so we walk the body in document order (regardless of the order
  // they appear in `analysis.findings`).
  const inSection = anchored
    .filter((row) => row.offset.section_index === section.idx)
    .sort((a, b) => a.offset.start - b.offset.start);

  const bodyStart = section.char_end - section.body.length;

  return (
    <section className="mb-8 last:mb-0" data-testid="source-section">
      <div className="font-mono text-[10px] tracking-[0.18em] uppercase text-burgundy font-semibold mb-1">
        § {section.number} — {section.title}
      </div>
      <h3 className="font-serif text-lg font-semibold text-ink mb-2">
        {section.title}
      </h3>
      <div
        className="font-serif text-sm leading-7 text-ink-soft"
        style={{ textAlign: 'justify', hyphens: 'auto' }}
      >
        {renderBodyWithHighlights({
          body: section.body,
          bodyStart,
          findings: inSection,
          onJump,
        })}
      </div>
    </section>
  );
}

type RenderArgs = {
  body: string;
  bodyStart: number;
  findings: AnchoredFinding[];
  onJump: (findingIndex: number) => void;
};

/**
 * Walk the section body and emit alternating plain text + highlight buttons.
 *
 * `bodyStart` is the absolute char offset of `body[0]` in the canonical
 * source_text coordinate system that `SourceOffset.start`/`end` use.
 *
 * If a highlight's local indices fall outside `[0, body.length]` (overflow
 * or negative), the highlight is skipped silently — the offset stage should
 * not produce these, but a defensive skip is cheaper than crashing the tab
 * for one bad row. (The Constitution VI banner already announces any
 * un-located finding.)
 */
function renderBodyWithHighlights({
  body,
  bodyStart,
  findings,
  onJump,
}: RenderArgs): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  let cursor = 0;

  for (const row of findings) {
    const localStart = row.offset.start - bodyStart;
    const localEnd = row.offset.end - bodyStart;

    if (
      localStart < cursor ||
      localStart < 0 ||
      localEnd > body.length ||
      localEnd <= localStart
    ) {
      // Overlaps, out-of-range, or empty — skip this highlight.
      continue;
    }

    if (localStart > cursor) {
      nodes.push(
        <span key={`txt-${cursor}`}>{body.slice(cursor, localStart)}</span>,
      );
    }

    const slice = body.slice(localStart, localEnd);
    const severity = row.finding.severity;
    nodes.push(
      <button
        key={`hl-${row.index}`}
        type="button"
        role="button"
        tabIndex={0}
        data-testid="source-highlight"
        data-finding-index={String(row.index)}
        data-severity={severity}
        aria-label={`Jump to finding: ${row.finding.title}`}
        onClick={() => onJump(row.index)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onJump(row.index);
          }
        }}
        className={[
          'inline px-0.5 rounded-sm cursor-pointer text-ink-soft text-left',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-burgundy focus-visible:ring-offset-2',
          SEVERITY_HIGHLIGHT[severity],
        ].join(' ')}
      >
        {slice}
      </button>,
    );

    cursor = localEnd;
  }

  if (cursor < body.length) {
    nodes.push(<span key={`txt-tail`}>{body.slice(cursor)}</span>);
  }

  return nodes;
}

export default Source;
