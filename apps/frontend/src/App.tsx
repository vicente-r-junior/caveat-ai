/**
 * Caveat AI — App shell.
 *
 * Owns the persistent chrome (Topbar at the top, DisclaimerFooter at the
 * bottom) and the React Router surface. The disclaimer is rendered here
 * deliberately so every route inherits it (Constitution IV — disclaimers
 * are part of the product and must appear on every screen with AI output).
 *
 * The active document context (filename + meta string for the topbar) and
 * the Topbar status pill state live at this level so any child route can
 * update them via the typed `Outlet` context without prop-drilling.
 */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  BrowserRouter,
  Outlet,
  Route,
  Routes,
  useOutletContext,
} from 'react-router-dom';
import { DisclaimerFooter } from './components/DisclaimerFooter';
import { Topbar } from './components/Topbar';
import { getHealth } from './api/health';
import { Upload } from './pages/Upload';
import { Processing } from './pages/Processing';
import { Review } from './pages/Review';

export type DocContext = { filename: string; meta?: string } | null;

export type AppContextValue = {
  setActiveDoc: (doc: DocContext) => void;
  setStatus: (status: 'idle' | 'working') => void;
};

/** Hook used by route components to update the persistent chrome. */
export function useAppContext(): AppContextValue {
  return useOutletContext<AppContextValue>();
}

function Shell(): JSX.Element {
  const [model, setModel] = useState<string | null>(null);
  const [activeDoc, setActiveDoc] = useState<DocContext>(null);
  const [status, setStatus] = useState<'idle' | 'working'>('idle');

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((data) => {
        if (cancelled) return;
        setModel(data.model);
      })
      .catch(() => {
        // Backend unreachable — Topbar's null-model branch already shows
        // a "Connecting…" pill, which is the honest empty state.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSetActiveDoc = useCallback((doc: DocContext) => {
    setActiveDoc(doc);
  }, []);
  const handleSetStatus = useCallback((next: 'idle' | 'working') => {
    setStatus(next);
  }, []);

  const ctx = useMemo<AppContextValue>(
    () => ({ setActiveDoc: handleSetActiveDoc, setStatus: handleSetStatus }),
    [handleSetActiveDoc, handleSetStatus],
  );

  return (
    <div className="min-h-screen flex flex-col bg-bg text-ink">
      <Topbar docContext={activeDoc} status={status} model={model} />
      <main className="flex-1 flex flex-col overflow-hidden">
        <Outlet context={ctx} />
      </main>
      <DisclaimerFooter />
    </div>
  );
}

export function App(): JSX.Element {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route path="/" element={<Upload />} />
          <Route path="/processing/:docId" element={<Processing />} />
          <Route path="/review/:docId" element={<Review />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
