import { useEffect, useState } from 'react';
import { apiGet } from './api/client';

type HealthResponse = {
  status: string;
  model: string;
};

type LoadState = 'loading' | 'ok' | 'error';

const STATUS_DOT: Record<LoadState, string> = {
  loading: 'bg-warn',
  ok: 'bg-safe',
  error: 'bg-danger',
};

const STATUS_LINE: Record<LoadState, string> = {
  loading: 'loading',
  ok: 'ok',
  error: 'unreachable',
};

export function App(): JSX.Element {
  const [state, setState] = useState<LoadState>('loading');
  const [model, setModel] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiGet<HealthResponse>('/health')
      .then((data) => {
        if (cancelled) return;
        setModel(data.model);
        setState('ok');
      })
      .catch(() => {
        if (cancelled) return;
        setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const pillLabel =
    state === 'ok' && model
      ? `Local · Gemma 4 · ${model}`
      : state === 'loading'
        ? 'Local · Connecting…'
        : 'Local · Backend unreachable';

  return (
    <main className="min-h-screen bg-bg flex items-center justify-center px-8 py-16">
      <section className="w-full max-w-xl flex flex-col items-center text-center gap-6">
        <p className="font-mono text-[10px] tracking-[0.18em] text-ink-muted uppercase">
          Sprint 0 — Scaffold
        </p>

        <h1 className="font-serif text-4xl font-semibold tracking-tight text-ink">
          Caveat AI
        </h1>

        <span
          className="font-mono text-[10px] tracking-[0.10em] uppercase bg-bg-soft border border-line rounded px-2.5 py-1 inline-flex items-center gap-2 text-ink-soft"
          data-testid="status-pill"
        >
          <span
            aria-hidden="true"
            className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT[state]}`}
          />
          {pillLabel}
        </span>

        <p className="text-ink-soft text-sm" data-testid="status-line">
          Backend status: {STATUS_LINE[state]}
        </p>

        <footer className="pt-8 mt-4 border-t border-line-soft w-full">
          <p className="font-mono text-[10px] tracking-[0.18em] text-ink-muted uppercase">
            AI-generated output — attorney review required
          </p>
        </footer>
      </section>
    </main>
  );
}
