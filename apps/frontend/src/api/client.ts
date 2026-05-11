/**
 * Tiny fetch wrapper for the Caveat AI backend.
 *
 * Constitution I (local-only): this module is the single chokepoint for
 * outbound HTTP from the React tree. It refuses absolute URLs at runtime
 * so a future bug, dependency, or copy-paste cannot accidentally exfil
 * a privileged document to an external host. All callers pass relative
 * paths like '/health'; this module prepends '/api' which the Vite dev
 * server (and the production FastAPI server) handles.
 */

const API_PREFIX = '/api';

class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function assertRelative(path: string): void {
  if (/^https?:\/\//i.test(path)) {
    throw new Error(
      `Refusing absolute URL "${path}". The frontend may only call the local backend ` +
        `via relative paths (Constitution I — local-only).`,
    );
  }
}

function buildUrl(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`;
  return `${API_PREFIX}${normalized}`;
}

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    // Surface the backend's `detail` verbatim when present so the UI can
    // render an honest message (Constitution VI). Falls back to the HTTP
    // status line when the body is not JSON.
    let message = `Request failed: ${response.status} ${response.statusText}`;
    try {
      const json = (await response.json()) as { detail?: unknown };
      if (typeof json.detail === 'string' && json.detail.trim() !== '') {
        message = json.detail;
      }
    } catch {
      // Body wasn't JSON; keep the generic message.
    }
    throw new ApiError(message, response.status);
  }
  return (await response.json()) as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  assertRelative(path);
  const response = await fetch(buildUrl(path), {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  return handle<T>(response);
}

export type ApiRequestOptions = {
  /** Optional AbortSignal threaded through to the underlying fetch. */
  signal?: AbortSignal;
};

export async function apiPost<T>(
  path: string,
  body: unknown,
  options?: ApiRequestOptions,
): Promise<T> {
  assertRelative(path);
  const response = await fetch(buildUrl(path), {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
    signal: options?.signal,
  });
  return handle<T>(response);
}

/**
 * Multipart upload variant — does NOT set Content-Type so the browser
 * (or undici in tests) attaches the correct multipart/form-data boundary.
 * Reuses {@link assertRelative} so the local-only guard still applies.
 */
export async function apiPostFormData<T>(
  path: string,
  body: FormData,
): Promise<T> {
  assertRelative(path);
  const response = await fetch(buildUrl(path), {
    method: 'POST',
    headers: { Accept: 'application/json' },
    body,
  });
  if (!response.ok) {
    // Try to surface the backend's `detail` field verbatim so the caller
    // can display it (Constitution VI — honest about what failed).
    let detail = `Request failed: ${response.status} ${response.statusText}`;
    try {
      const json = (await response.json()) as { detail?: unknown };
      if (typeof json.detail === 'string' && json.detail.trim() !== '') {
        detail = json.detail;
      }
    } catch {
      // Body wasn't JSON; keep the generic message.
    }
    throw new ApiError(detail, response.status);
  }
  return (await response.json()) as T;
}

export { ApiError };
