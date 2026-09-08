export type ApiErrorKind = 'network' | 'unauthorized' | 'validation' | 'conflict' | 'server' | 'unavailable' | 'unknown';

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly kind: ApiErrorKind,
    public readonly status?: number,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function errorKind(status: number): ApiErrorKind {
  if (status === 401 || status === 403) return 'unauthorized';
  if (status === 400 || status === 422) return 'validation';
  if (status === 409) return 'conflict';
  if (status === 502 || status === 503 || status === 504) return 'unavailable';
  if (status >= 500) return 'server';
  return 'unknown';
}

export async function request(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (!headers.has('accept')) headers.set('accept', 'application/json');
  try {
    const response = await fetch(input, { ...init, headers });
    if (response.ok) return response;
    const body = await response.json().catch(() => null) as { detail?: unknown } | null;
    const detail = typeof body?.detail === 'string' ? body.detail : `Request failed with HTTP ${response.status}.`;
    throw new ApiError(detail, errorKind(response.status), response.status);
  } catch (error) {
    if (error instanceof ApiError || error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(error instanceof Error ? error.message : 'Network request failed.', 'network');
  }
}

export async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await request(input, init);
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}

export async function requestVoid(input: RequestInfo | URL, init?: RequestInit): Promise<void> {
  await request(input, init);
}

export function jsonRequest(method: 'POST' | 'PUT' | 'PATCH', body: unknown): RequestInit {
  return {
    method,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  };
}
