/**
 * Review page — prototype screen 04.
 *
 * Sidebar (260px) + main column with tab bar. Sprint 2 only ships the
 * Findings tab; Client summary, Source, and Chat render TabPlaceholder.
 *
 * On hard refresh the router state is empty; we re-fetch the analysis
 * via `analyzeDocument` (slow on E4B — Sprint 4's findings router will
 * make this instant via local persistence).
 */

import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { useAppContext } from '../App';
import { ApiError } from '../api/client';
import { type AnalyzeResponse, analyzeDocument } from '../api/analyze';
import { TabPlaceholder } from '../components/TabPlaceholder';
import { Findings } from '../tabs/Findings';

type TabKey = 'findings' | 'summary' | 'source' | 'chat';

type LocationState = {
  analysis?: AnalyzeResponse;
  filename?: string;
} | null;

export function Review(): JSX.Element {
  const { docId } = useParams<{ docId: string }>();
  const location = useLocation();
  const { setActiveDoc, setStatus } = useAppContext();

  const initialState = (location.state ?? null) as LocationState;
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(
    initialState?.analysis ?? null,
  );
  const [filename, setFilename] = useState<string>(
    initialState?.filename ?? 'Document',
  );
  const [recoverError, setRecoverError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>('findings');

  // Hard-refresh recovery: no router state → re-run analyze.
  useEffect(() => {
    if (analysis || !docId) return;
    let cancelled = false;
    setStatus('working');
    analyzeDocument(docId)
      .then((result) => {
        if (cancelled) return;
        setAnalysis(result);
        setStatus('idle');
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message =
          err instanceof ApiError
            ? err.message
            : err instanceof Error
              ? err.message
              : 'Could not load analysis';
        setRecoverError(message);
        setStatus('idle');
      });
    return () => {
      cancelled = true;
    };
  }, [analysis, docId, setStatus]);

  // Topbar context: filename + contract type + page count when we have it.
  useEffect(() => {
    const meta = analysis
      ? [analysis.contract_type ?? null]
          .filter((x): x is string => Boolean(x))
          .join(' · ') || undefined
      : undefined;
    setActiveDoc({ filename, meta });
  }, [analysis, filename, setActiveDoc]);

  // Counts for the tab badges.
  const findingsCount = useMemo(
    () => (analysis ? analysis.findings.length : 0),
    [analysis],
  );
  const highCount = useMemo(
    () =>
      analysis
        ? analysis.findings.filter((f) => f.severity === 'high').length
        : 0,
    [analysis],
  );
  const medCount = useMemo(
    () =>
      analysis
        ? analysis.findings.filter((f) => f.severity === 'medium').length
        : 0,
    [analysis],
  );

  // Sync filename if router state arrives later via re-fetch.
  useEffect(() => {
    if (initialState?.filename && filename === 'Document') {
      setFilename(initialState.filename);
    }
  }, [initialState?.filename, filename]);

  if (recoverError) {
    return (
      <div className="flex-1 flex items-center justify-center px-8 py-12">
        <div
          className="max-w-[640px] bg-danger-soft border border-danger rounded-md p-6"
          role="alert"
          data-testid="review-error"
        >
          <h2 className="font-serif text-[22px] font-semibold text-ink mb-2">
            Could not load this analysis.
          </h2>
          <p className="text-sm text-ink-soft mb-4 leading-relaxed">
            {recoverError}
          </p>
          <Link
            to="/"
            className="font-sans text-sm text-burgundy underline underline-offset-4 hover:no-underline"
          >
            ← Back to upload
          </Link>
        </div>
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="flex-1 flex items-center justify-center px-8 py-12">
        <div className="max-w-[420px] text-center">
          <p className="font-mono text-[10px] tracking-[0.18em] uppercase text-burgundy mb-3">
            Re-running analysis
          </p>
          <p className="font-serif italic text-xl text-ink-soft leading-relaxed">
            Re-running the analysis on the local model…
          </p>
          <p className="font-sans text-xs text-ink-muted mt-4 leading-relaxed">
            On the E4B fallback model this takes 30–180s. There&rsquo;s no
            results cache yet — Sprint 4 will make refreshes instant via the
            local findings store.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      className="flex-1 grid grid-cols-[260px_1fr] overflow-hidden"
      data-testid="review-grid"
    >
      {/* Sidebar */}
      <aside className="bg-bg-soft border-r border-line overflow-y-auto flex flex-col">
        <div className="p-4">
          <div className="font-mono text-[10px] tracking-[0.12em] uppercase text-ink-muted mb-2.5 flex justify-between items-center">
            <span>Documents</span>
            <span className="text-burgundy font-semibold">1</span>
          </div>

          <div
            className="bg-white border border-ink rounded-md p-3 cursor-pointer mb-1 shadow-[0_1px_2px_rgba(0,0,0,0.04)]"
            data-testid="sidebar-doc-active"
          >
            <div className="flex items-center gap-2 mb-1">
              <div className="w-[22px] h-[26px] bg-burgundy-soft border border-burgundy rounded-sm grid place-items-center font-mono text-[8px] font-semibold text-burgundy shrink-0">
                PDF
              </div>
              <div className="text-[13px] font-medium text-ink leading-tight flex-1 overflow-hidden text-ellipsis whitespace-nowrap">
                {filename}
              </div>
            </div>
            <div className="font-mono text-[10px] text-ink-muted ml-[30px] flex gap-2">
              {highCount > 0 ? (
                <span className="text-danger font-semibold">
                  {highCount}↑
                </span>
              ) : null}
              {medCount > 0 ? (
                <span className="text-warn font-semibold">{medCount}</span>
              ) : null}
              <span>· {analysis.findings.length}f</span>
            </div>
          </div>

          <button
            type="button"
            disabled
            title="Multi-document support arrives in Sprint 4"
            data-testid="sidebar-add-doc"
            className="w-full p-3 mt-2 border-[1.5px] border-dashed border-line rounded-md bg-transparent text-ink-muted text-[13px] font-sans cursor-not-allowed opacity-60"
          >
            + Add document
          </button>
        </div>

        <div className="mt-auto p-4 border-t border-line bg-white">
          <div
            className="font-mono text-[10px] uppercase tracking-[0.10em] text-ink-muted leading-relaxed"
            data-testid="sidebar-privacy-note"
          >
            <strong className="text-burgundy font-semibold block mb-1">
              Privileged work product
            </strong>
            Nothing leaves this machine. Run airplane mode if you&rsquo;d
            like — it doesn&rsquo;t matter.
          </div>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex flex-col overflow-hidden">
        <nav className="flex bg-bg border-b border-line px-6 gap-1 items-end h-12 shrink-0">
          <TabButton
            label="Findings"
            isActive={activeTab === 'findings'}
            onClick={() => setActiveTab('findings')}
            badgeText={String(findingsCount)}
            badgeDanger={highCount > 0}
            testId="tab-findings"
          />
          <TabButton
            label="Client summary"
            isActive={activeTab === 'summary'}
            onClick={() => setActiveTab('summary')}
            testId="tab-summary"
          />
          <TabButton
            label="Source"
            isActive={activeTab === 'source'}
            onClick={() => setActiveTab('source')}
            badgeText={`${analysis.findings.length > 0 ? '—' : '0'}p`}
            testId="tab-source"
          />
          <TabButton
            label="Chat"
            isActive={activeTab === 'chat'}
            onClick={() => setActiveTab('chat')}
            badgeText="0"
            testId="tab-chat"
          />
          <div className="flex-1" />
          <div className="flex gap-2 pb-2">
            <button
              type="button"
              disabled
              title="Custom playbooks and re-analysis arrive in Sprint 5"
              data-testid="tab-action-reanalyze"
              className="font-sans text-[13px] font-medium px-3.5 py-2 border border-line rounded-md bg-bg text-ink-muted opacity-60 cursor-not-allowed"
            >
              Re-analyze
            </button>
          </div>
        </nav>

        <div className="flex-1 overflow-y-auto bg-bg">
          {activeTab === 'findings' ? (
            <Findings analysis={analysis} />
          ) : activeTab === 'summary' ? (
            <TabPlaceholder
              sprintNumber={3}
              tabNumber={2}
              title="Client summary"
              description="A plain-English memo for your client — what the contract is, what they're committing to, the top 3 risks, and a clear recommendation. Lands in Sprint 3."
            />
          ) : activeTab === 'source' ? (
            <TabPlaceholder
              sprintNumber={3}
              tabNumber={3}
              title="Source viewer"
              description="The full source PDF, with cited passages highlighted in burgundy alongside the relevant findings. Lands in Sprint 3."
            />
          ) : (
            <TabPlaceholder
              sprintNumber={4}
              tabNumber={4}
              title="Multi-document chat"
              description="Ask questions across up to 5 loaded contracts at once, with citations from each. Streaming chat with the local Gemma 4 model. Lands in Sprint 4."
            />
          )}
        </div>
      </div>
    </div>
  );
}

type TabButtonProps = {
  label: string;
  isActive: boolean;
  onClick: () => void;
  badgeText?: string;
  badgeDanger?: boolean;
  testId?: string;
};

function TabButton({
  label,
  isActive,
  onClick,
  badgeText,
  badgeDanger = false,
  testId,
}: TabButtonProps): JSX.Element {
  const baseClass = [
    'px-4 h-12 border-b-2 font-medium text-sm inline-flex items-center gap-2 -mb-px transition-colors',
    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-burgundy focus-visible:ring-offset-2',
    isActive
      ? 'text-ink border-burgundy'
      : 'text-ink-muted border-transparent hover:text-ink',
  ].join(' ');
  const badgeClass = [
    'font-mono text-[10px] font-semibold px-1.5 py-0.5 rounded-sm',
    badgeDanger
      ? 'bg-danger text-white'
      : isActive
        ? 'bg-burgundy text-white'
        : 'bg-bg-tint text-ink-soft',
  ].join(' ');
  return (
    <button
      type="button"
      onClick={onClick}
      className={baseClass}
      data-testid={testId}
      aria-current={isActive ? 'page' : undefined}
    >
      {label}
      {badgeText ? <span className={badgeClass}>{badgeText}</span> : null}
    </button>
  );
}

export default Review;
