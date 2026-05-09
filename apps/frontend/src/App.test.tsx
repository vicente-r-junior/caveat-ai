import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { App } from './App';

describe('<App />', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders the heading, eyebrow, and disclaimer', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ status: 'ok', model: 'gemma4:e4b' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    render(<App />);

    expect(
      screen.getByRole('heading', { level: 1, name: /caveat ai/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/sprint 0 — scaffold/i)).toBeInTheDocument();
    expect(
      screen.getByText(/ai-generated output — attorney review required/i),
    ).toBeInTheDocument();

    // Drain the in-flight /health request so React's act warning stays quiet.
    await screen.findByText(/backend status: ok/i);
  });

  it('shows backend status ok and the model name once /api/health resolves', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ status: 'ok', model: 'gemma4:e4b' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    render(<App />);

    expect(await screen.findByText(/backend status: ok/i)).toBeInTheDocument();
    const pill = await screen.findByTestId('status-pill');
    expect(pill).toHaveTextContent(/gemma4:e4b/);
    expect(pill).toHaveTextContent(/local · gemma 4/i);
  });

  it('shows backend status unreachable when /api/health rejects', async () => {
    fetchMock.mockRejectedValueOnce(new Error('network down'));

    render(<App />);

    expect(
      await screen.findByText(/backend status: unreachable/i),
    ).toBeInTheDocument();
    const pill = await screen.findByTestId('status-pill');
    expect(pill).toHaveTextContent(/local · backend unreachable/i);
  });

  it('shows the loading state before the request resolves', () => {
    // Never resolves — exercises the initial 'loading' branch deterministically.
    fetchMock.mockImplementationOnce(() => new Promise(() => {}));

    render(<App />);

    expect(screen.getByText(/backend status: loading/i)).toBeInTheDocument();
    expect(screen.getByTestId('status-pill')).toHaveTextContent(
      /local · connecting/i,
    );
  });
});
