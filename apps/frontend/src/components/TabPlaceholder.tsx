/**
 * Coming-soon panel rendered on Review tabs that don't ship in Sprint 2.
 *
 * Per the prototype's editorial tone: serif title, mono eyebrow, short
 * paragraph in ink-soft. We name the future sprint explicitly so a
 * curious user (or reviewer) can map the tab to its delivery sprint.
 */

type TabPlaceholderProps = {
  sprintNumber: number;
  /** Which tab number on the Review screen this placeholder corresponds to. */
  tabNumber?: number;
  title: string;
  description: string;
};

export function TabPlaceholder({
  sprintNumber,
  tabNumber,
  title,
  description,
}: TabPlaceholderProps): JSX.Element {
  return (
    <div
      className="max-w-[600px] mx-auto px-8 py-20 text-center"
      data-testid="tab-placeholder"
    >
      <p className="font-mono text-[10px] tracking-[0.18em] uppercase text-burgundy mb-3">
        Roadmap
        {tabNumber ? ` · Tab 0${tabNumber}` : ''}
      </p>
      <h2 className="font-serif text-3xl font-semibold tracking-tight text-ink mb-4 leading-tight">
        Coming in Sprint {sprintNumber} — <em className="italic font-normal text-burgundy">{title}.</em>
      </h2>
      <p className="text-base text-ink-soft leading-relaxed">{description}</p>
    </div>
  );
}

export default TabPlaceholder;
