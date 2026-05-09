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
    throw new ApiError(
      `Request failed: ${response.status} ${response.statusText}`,
      response.status,
    );
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

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  assertRelative(path);
  const response = await fetch(buildUrl(path), {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });
  return handle<T>(response);
}

export { ApiError };
