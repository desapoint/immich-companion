export interface ApiRequestInit extends Omit<RequestInit, 'body'> {
  body?: BodyInit | null;
  json?: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string | null;

  constructor(message: string, status: number, detail: string | null = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function buildRequestInit(init: ApiRequestInit = {}): RequestInit {
  const { json, ...requestInit } = init;
  const headers = new Headers(requestInit.headers);

  if (!headers.has('Accept')) headers.set('Accept', 'application/json');

  let body = requestInit.body;
  if (json !== undefined) {
    if (body !== undefined && body !== null) {
      throw new TypeError('Use either body or json when making an API request, not both.');
    }
    if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    body = JSON.stringify(json);
  }

  return { ...requestInit, headers, body };
}

async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const contentType = response.headers.get('content-type') ?? '';
    if (contentType.includes('json')) {
      const body = await response.json() as unknown;
      if (typeof body === 'string' && body.trim()) return body.trim();
      if (body && typeof body === 'object' && 'detail' in body) {
        const detail = (body as { detail?: unknown }).detail;
        if (typeof detail === 'string' && detail.trim()) return detail.trim();
      }
      return null;
    }

    const text = (await response.text()).trim();
    return text || null;
  } catch {
    return null;
  }
}

export async function request(
  input: RequestInfo | URL,
  init: ApiRequestInit = {},
): Promise<Response> {
  const response = await fetch(input, buildRequestInit(init));
  if (response.ok) return response;

  const detail = await readErrorDetail(response);
  throw new ApiError(
    detail ?? `Request failed with HTTP ${response.status}.`,
    response.status,
    detail,
  );
}

export async function requestJson<T>(
  input: RequestInfo | URL,
  init: ApiRequestInit = {},
): Promise<T> {
  const response = await request(input, init);
  return await response.json() as T;
}

export async function requestVoid(
  input: RequestInfo | URL,
  init: ApiRequestInit = {},
): Promise<void> {
  await request(input, init);
}
