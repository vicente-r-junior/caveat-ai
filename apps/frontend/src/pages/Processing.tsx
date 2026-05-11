/**
 * Processing page — prototype screen 03.
 *
 * Two parallel tracks share this screen:
 *
 *   1. The real `analyzeDocument(docId)` HTTP call, fired on mount.
 *   2. A 6-stage timer-driven pipeline UI calibrated to feel honest about
 *      what the backend is doing. Stage durations come from observed E4B
 *      timings; we intentionally do NOT auto-advance past the LAST stage
 *      so a slow backend never lands on "complete" while still in flight
 *      (Constitution VI — honesty over polish).
 *
 * On resolve we mark all stages done, then navigate to /review/{id}
 * passing the analysis through router state to avoid a re-fetch.
 *
 * On reject we render a verbatim error pane with a Back link — no auto-
 * retry, no fake recovery state.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useAppContext } from '../App';
import { ApiError } from '../api/client';
import { type AnalyzeResponse, analyzeDocument } from '../api/analyze';

type StageStatus = 'done' | 'active' | 'pending';

type Stage = {
  key: string;
  label: string;
  durationMs: number;
};

const STAGES: Stage[] = [
  {
    key: 'parse',
    label: 'Parse PDF and extract structured sections',
    durationMs: 1500,
  },
  { key: 'classify', label: 'Classify contract type', durationMs: 5000 },
  {
    key: 'playbook',
    label: 'Load playbook from local library',
    durationMs: 500,
  },
  {
    key: 'analyze',
    label: 'Identify risk clauses and missing provisions',
    durationMs: 70000,
  },
  {
    key: 'validate',
    label: 'Validate citations against source text',
    durationMs: 2000,
  },
  {
    key: 'summary',
    label: 'Generate plain-English client summary',
    durationMs: 30000,
  },
];

type LocationState = {
  filename?: string;
  pageCount?: number;
} | null;

export function Processing(): JSX.Element {
  const { docId } = useParams<{ docId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { setActiveDoc, setStatus } = useAppContext();

  const state = (location.state ?? null) as LocationState;
  const filename = state?.filename ?? 'Document';
  const pageCount = state?.pageCount;

  /** zero-indexed: index of the currently-active stage (0..STAGES.length-1).
   *  When the analysis succeeds we set this to STAGES.length to mark all done. */
  const [currentStage, setCurrentStage] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Hold the resolved analysis in a ref so the navigate effect can read it
  // without becoming a dependency of the timer effect.
  const analysisRef = useRef<AnalyzeResponse | null>(null);
  const completedRef = useRef(false);
  // Sprint 3 fixup-2: dedupe POST /api/analyze/{docId} under StrictMode's
  // dev double-mount. The ref is set *before* the fetch dispatch, so the
  // second mount of the analyze effect short-circuits without firing a
  // second HTTP request. Scoped by docId so navigating to a different
  // document still re-fetches.
  const fetchedForDocIdRef = useRef<string | null>(null);

  // Keep the topbar in sync. Working pulse stays on for the duration.
  useEffect(() => {
    setActiveDoc({
      filename,
      meta: pageCount ? `${pageCount} pages · analyzing` : 'analyzing',
    });
    setStatus('working');
    return () => {
      setStatus('idle');
    };
  }, [filename, pageCount, setActiveDoc, setStatus]);

  // Kick off the real analysis on mount.
  //
  // The ref guard (`fetchedForDocIdRef`) is set *before* the fetch
  // dispatch so the second StrictMode mount short-circuits without
  // constructing an AbortController or hitting the network.
  //
  // We intentionally do NOT abort on cleanup. Under StrictMode the
  // first cleanup runs *between* the two mounts of the same effect;
  // aborting there would kill the only fetch we ever made (the second
  // mount short-circuits via the ref and never re-dispatches). The
  // `controller.signal.aborted` checks in .then/.catch remain as
  // defensive guards — always false in practice with this design.
  // Processing only unmounts on success (navigate to /review) or when
  // an error pane replaces it (no further fetch), so leaking an
  // in-flight fetch on unmount is not a real concern; React 18
  // tolerates the resulting refs + setState calls on the unmounted
  // component without warnings.
  useEffect(() => {
    if (!docId) return;
    if (fetchedForDocIdRef.current === docId) return;
    fetchedForDocIdRef.current = docId;

    const controller = new AbortController();
    analyzeDocument(docId, { signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) return;
        analysisRef.current = result;
        completedRef.current = true;
        // Fast-forward all stages to "done" — the backend beat the timer.
        setCurrentStage(STAGES.length);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        if (err instanceof DOMException && err.name === 'AbortError') return;
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : 'Analysis failed';
        completedRef.current = true;
        setError(message);
      });
  }, [docId]);

  // Timer-driven stage advance. Holds on the LAST stage (index N-1) until
  // the backend resolves — never auto-completes on the timer alone.
  useEffect(() => {
    if (error) return undefined;
    if (currentStage >= STAGES.length - 1) return undefined;
    const timer = window.setTimeout(() => {
      // Only advance if we haven't already fast-forwarded via the response.
      if (completedRef.current) return;
      setCurrentStage((s) => Math.min(s + 1, STAGES.length - 1));
    }, STAGES[currentStage]!.durationMs);
    return () => {
      window.clearTimeout(timer);
    };
  }, [currentStage, error]);

  // When all stages are done (currentStage === STAGES.length) and the
  // analysis is in hand, navigate to review.
  useEffect(() => {
    if (error) return;
    if (currentStage < STAGES.length) return;
    const analysis = analysisRef.current;
    if (!analysis || !docId) return;
    navigate(`/review/${docId}`, {
      replace: true,
      state: { analysis, filename },
    });
  }, [currentStage, docId, error, filename, navigate]);

  const stageStatuses = useMemo<StageStatus[]>(() => {
    return STAGES.map((_, i) => {
      if (i < currentStage) return 'done';
      if (i === currentStage && currentStage < STAGES.length) return 'active';
      if (currentStage >= STAGES.length) return 'done';
      return 'pending';
    });
  }, [currentStage]);

  if (error) {
    return (
      <div className="flex-1 flex items-center justify-center px-8 py-12 overflow-y-auto">
        <div className="max-w-[640px] w-full">
          <div
            className="bg-danger-soft border border-danger rounded-md p-6"
            role="alert"
            data-testid="processing-error"
          >
            <h2 className="font-serif text-[22px] font-semibold text-ink mb-2 leading-tight">
              Analysis failed.
            </h2>
            <p className="text-sm text-ink-soft mb-4 leading-relaxed">
              {error}
            </p>
            <Link
              to="/"
              className="font-sans text-sm text-burgundy underline underline-offset-4 hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-burgundy focus-visible:ring-offset-2 rounded-sm"
            >
              ← Back to upload
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex items-center justify-center px-8 py-12 overflow-y-auto">
      <div className="max-w-[640px] w-full">
        <div
          className="inline-flex items-center gap-3 px-4 py-2.5 bg-bg-soft border border-line rounded-md mb-8 font-mono text-[11px]"
          data-testid="processing-doc-pill"
        >
          <span className="text-ink font-semibold">{filename}</span>
          <span className="text-ink-muted border-l border-line pl-3">
            {pageCount ? `${pageCount} pages · ` : ''}classifying…
          </span>
        </div>

        <h2 className="font-serif text-[44px] font-semibold leading-[1.05] tracking-[-0.02em] mb-3">
          Reading{' '}
          <em className="italic text-burgundy font-normal">carefully.</em>
        </h2>
        <p className="text-base text-ink-soft mb-9 leading-relaxed">
          Gemma 4 is parsing your contract and cross-referencing the playbook.
          First analysis after starting may take 3–5 min while Gemma loads
          into RAM; subsequent analyses are 30–120s. Estimated stages —
          actual timing varies.
        </p>

        <div
          className="bg-bg border border-line rounded-lg p-2 mb-7"
          data-testid="pipeline"
        >
          {STAGES.map((stage, i) => {
            const status = stageStatuses[i]!;
            const num = String(i + 1).padStart(2, '0');
            const stepClass = [
              'grid grid-cols-[32px_1fr_auto] gap-3.5 items-center px-4 py-3.5 rounded text-sm transition-colors',
              status === 'done' ? 'text-ink-muted' : '',
              status === 'active'
                ? 'bg-bg-soft text-ink font-medium'
                : '',
              status === 'pending' ? 'text-ink-muted opacity-50' : '',
            ].join(' ');
            const numClass = [
              'font-mono text-[11px] text-center font-medium',
              status === 'done' ? 'text-safe' : '',
              status === 'active' ? 'text-burgundy font-bold' : '',
              status === 'pending' ? 'text-ink-muted' : '',
            ].join(' ');
            const timeClass = [
              'font-mono text-[10px] uppercase tracking-[0.10em]',
              status === 'active'
                ? 'text-burgundy font-semibold inline-flex items-center gap-1.5'
                : 'text-ink-muted',
            ].join(' ');
            return (
              <div
                key={stage.key}
                className={stepClass}
                data-testid={`pipe-step-${stage.key}`}
                data-status={status}
              >
                <span className={numClass} aria-hidden="true">
                  {status === 'done' ? '✓' : num}
                </span>
                <span>{stage.label}</span>
                <span className={timeClass}>
                  {status === 'done'
                    ? 'done'
                    : status === 'active'
                      ? 'running'
                      : 'queued'}
                  {status === 'active' ? (
                    <span
                      aria-hidden="true"
                      className="w-1.5 h-1.5 rounded-full bg-burgundy animate-pulse"
                    />
                  ) : null}
                </span>
              </div>
            );
          })}
        </div>

        <div
          className="border-l-[3px] border-burgundy bg-burgundy-soft p-3.5 rounded-r-md text-[13px] text-ink-soft leading-relaxed"
          data-testid="processing-note"
        >
          <strong className="text-burgundy font-semibold">
            Privileged work product.
          </strong>{' '}
          Computation is happening on this device only. You can disconnect
          from Wi-Fi without affecting the result.
        </div>
      </div>
    </div>
  );
}

export default Processing;
