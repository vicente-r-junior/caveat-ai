/**
 * Persistent top header — brand + AI tag + active-document context line +
 * status pills. Shared across every screen via the App shell.
 *
 * Visual ref: docs/caveat-prototype-v3.html `.topbar` block.
 */

type TopbarProps = {
  docContext?: { filename: string; meta?: string } | null;
  status?: 'idle' | 'working';
  /** Model name from /api/health; null while connecting. */
  model?: string | null;
};

export function Topbar({
  docContext = null,
  status = 'idle',
  model = null,
}: TopbarProps): JSX.Element {
  const statusLabel =
    model === null ? 'Local · Connecting…' : `Local · Gemma 4 · ${model}`;
  const isWorking = status === 'working';

  return (
    <header
      className="h-14 bg-bg border-b border-line flex items-center px-6 gap-6 shrink-0"
      data-testid="topbar"
    >
      <div className="flex items-baseline gap-2">
        <span className="font-serif text-xl font-semibold tracking-tight italic">
          Caveat
        </span>
        <span
          className="font-mono text-[9px] text-burgundy uppercase tracking-[0.18em] border border-burgundy px-1.5 py-0.5 rounded-sm font-medium"
          data-testid="topbar-ai-tag"
        >
          AI
        </span>
      </div>
      <div className="w-px h-6 bg-line" aria-hidden="true" />
      <div
        className="text-sm text-ink-soft font-medium [&_em]:not-italic [&_em]:text-ink-muted"
        data-testid="topbar-doc"
      >
        {docContext ? (
          <>
            {docContext.filename}
            {docContext.meta ? <em> · {docContext.meta}</em> : null}
          </>
        ) : (
          <em>No documents loaded</em>
        )}
      </div>
      <div className="ml-auto flex items-center gap-4">
        <span
          className={[
            'font-mono text-[10px] uppercase tracking-[0.10em] text-ink-muted',
            'inline-flex items-center gap-1.5 px-2.5 py-1 bg-bg-soft border border-line rounded',
          ].join(' ')}
          data-testid="topbar-status-pill"
        >
          <span
            aria-hidden="true"
            className={[
              'w-1.5 h-1.5 rounded-full',
              isWorking ? 'bg-warn animate-pulse' : 'bg-safe',
            ].join(' ')}
          />
          {statusLabel}
        </span>
        <span
          className={[
            'font-mono text-[10px] uppercase tracking-[0.10em] text-ink-muted',
            'inline-flex items-center gap-1.5 px-2.5 py-1 bg-bg-soft border border-line rounded',
          ].join(' ')}
        >
          <span
            aria-hidden="true"
            className="w-1.5 h-1.5 rounded-full bg-safe"
          />
          0 network requests
        </span>
      </div>
    </header>
  );
}

export default Topbar;
