/**
 * App shell tests — Sprint 2.
 *
 * The App component wraps everything in <BrowserRouter>; for the unit tests
 * we want to drive different routes deterministically. We swap BrowserRouter
 * for MemoryRouter via vi.mock and toggle the entry path through a module-
 * scoped `currentEntries` variable that each test sets before render().
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type React from 'react';

// Module-scoped initial entries; each test sets this before calling render.
let currentEntries: string[] = ['/'];

vi.mock('react-router-dom', async (importOriginal) => {
  const mod =
    await importOriginal<typeof import('react-router-dom')>();
  return {
    ...mod,
    BrowserRouter: ({ children }: { children: React.ReactNode }) => (
      <mod.MemoryRouter initialEntries={currentEntries}>
        {children}
      </mod.MemoryRouter>
    ),
  };
});

// Mock the API modules so no real fetch ever fires from the App tree.
vi.mock('./api/health', () => ({
  getHealth: vi
    .fn()
    .mockResolvedValue({ status: 'ok', model: 'gemma4:e4b' }),
}));

vi.mock('./api/documents', () => ({
  listDocuments: vi.fn().mockResolvedValue([]),
  uploadDocument: vi.fn(),
}));

vi.mock('./api/analyze', () => ({
  analyzeDocument: vi.fn().mockResolvedValue({
    document_id: 'abc',
    contract_type: 'MSA',
    findings: [],
    client_summary: {
      what_this_contract_is: '',
      what_youre_committing_to: '',
      biggest_risks: [],
      recommendation: '',
      disclaimer: 'AI-generated output — attorney review required.',
    },
    warnings: [],
    elapsed_seconds: 0,
    source_sections: [],
  }),
}));

import { App } from './App';

describe('<App /> shell', () => {
  beforeEach(() => {
    currentEntries = ['/'];
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('renders the disclaimer footer on every route', async () => {
    currentEntries = ['/'];
    render(<App />);
    expect(
      screen.getByText(/AI-generated output.*attorney review required/i),
    ).toBeInTheDocument();
    // Drain the in-flight /health request so React's act warning stays quiet.
    await screen.findByTestId('topbar-status-pill');
  });

  it('renders the topbar brand and AI tag', async () => {
    currentEntries = ['/'];
    render(<App />);
    expect(screen.getByText('Caveat')).toBeInTheDocument();
    expect(screen.getByTestId('topbar-ai-tag')).toHaveTextContent(/^AI$/);
    await screen.findByTestId('topbar-status-pill');
  });

  it('renders the Upload page on "/" — hero copy visible', async () => {
    currentEntries = ['/'];
    render(<App />);
    expect(screen.getByText(/Read the contract\./i)).toBeInTheDocument();
    expect(screen.getByText(/Keep the secret\./i)).toBeInTheDocument();
    await screen.findByTestId('topbar-status-pill');
  });

  it('renders the Processing page on /processing/:docId', async () => {
    currentEntries = ['/processing/abc'];
    render(<App />);
    expect(screen.getByText(/Reading/i)).toBeInTheDocument();
    expect(screen.getByText(/carefully\./i)).toBeInTheDocument();
    await screen.findByTestId('topbar-status-pill');
  });

  it('renders the Review page on /review/:docId (uses re-fetched analysis)', async () => {
    currentEntries = ['/review/abc'];
    render(<App />);
    // Review has no router state on this entry, so it re-fetches via the
    // mocked analyzeDocument. After resolution the tab bar appears.
    expect(await screen.findByTestId('tab-findings')).toBeInTheDocument();
    expect(screen.getByTestId('review-grid')).toBeInTheDocument();
  });

  it('topbar status pill shows the model name once /api/health resolves', async () => {
    currentEntries = ['/'];
    render(<App />);
    const pill = await screen.findByTestId('topbar-status-pill');
    // Wait for the model to populate (the pill flips from "Connecting…" to
    // "Local · Gemma 4 · gemma4:e4b").
    await vi.waitFor(() => {
      expect(pill).toHaveTextContent(/gemma4:e4b/);
    });
    expect(pill).toHaveTextContent(/local · gemma 4/i);
  });
});
