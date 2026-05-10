import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiGet, apiPost, apiPostFormData } from './client';

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

describe('apiPostFormData', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('prepends /api and sends FormData without setting Content-Type', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({ document_id: 'doc-1', filename: 'x.pdf' }),
        {
          status: 201,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    );

    const form = new FormData();
    form.append('file', new Blob(['%PDF-1.4'], { type: 'application/pdf' }));

    const result = await apiPostFormData<{ document_id: string }>(
      '/documents/',
      form,
    );

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe('/api/documents/');
    expect(init.method).toBe('POST');
    expect(init.body).toBe(form);
    // The browser sets the multipart boundary; our wrapper MUST NOT set it.
    expect(init.headers).toMatchObject({ Accept: 'application/json' });
    expect(init.headers).not.toHaveProperty('Content-Type');
    expect(result).toEqual({ document_id: 'doc-1', filename: 'x.pdf' });
  });

  it('refuses absolute URLs (Constitution I)', async () => {
    const form = new FormData();
    await expect(
      apiPostFormData('http://evil.com/exfil', form),
    ).rejects.toThrow(/Refusing absolute URL/);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('throws ApiError with the backend `detail` on non-2xx', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Only PDF files are accepted' }), {
        status: 415,
        statusText: 'Unsupported Media Type',
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    const form = new FormData();
    await expect(
      apiPostFormData('/documents/', form),
    ).rejects.toMatchObject({
      name: 'ApiError',
      status: 415,
      message: 'Only PDF files are accepted',
    });
  });

  it('falls back to a generic message when the body is not JSON', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response('not json', {
        status: 500,
        statusText: 'Internal Server Error',
      }),
    );

    const form = new FormData();
    await expect(
      apiPostFormData('/documents/', form),
    ).rejects.toBeInstanceOf(ApiError);
  });
});
