import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiGet, apiPost } from './client';

describe('apiGet', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('prepends /api and calls fetch with the relative path', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const result = await apiGet<{ status: string }>('/health');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe('/api/health');
    expect(init).toMatchObject({ method: 'GET' });
    expect(result).toEqual({ status: 'ok' });
  });

  it('refuses an absolute http URL (Constitution I)', async () => {
    await expect(apiGet('http://evil.com/exfil')).rejects.toThrow(
      /Refusing absolute URL/,
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('refuses an absolute https URL (Constitution I)', async () => {
    await expect(apiGet('https://evil.com/exfil')).rejects.toThrow(
      /Refusing absolute URL/,
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('throws ApiError on non-2xx', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('boom', { status: 500, statusText: 'Internal Server Error' }),
    );

    await expect(apiGet('/health')).rejects.toBeInstanceOf(ApiError);
  });

  it('normalises a path without a leading slash', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({}), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await apiGet('health');

    const [url] = fetchMock.mock.calls[0]!;
    expect(url).toBe('/api/health');
  });
});

describe('apiPost', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('serialises the body and sets JSON headers', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    await apiPost('/analyze', { documentId: 'abc' });

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe('/api/analyze');
    expect(init.method).toBe('POST');
    expect(init.body).toBe(JSON.stringify({ documentId: 'abc' }));
    expect(init.headers).toMatchObject({
      'Content-Type': 'application/json',
      Accept: 'application/json',
    });
  });

  it('refuses absolute URLs', async () => {
    await expect(apiPost('http://evil.com', {})).rejects.toThrow(
      /Refusing absolute URL/,
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
