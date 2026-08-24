import type {
  CapabilitiesResponse,
  HealthResponse,
  StatusSnapshot,
  VersionResponse,
} from '../types/status';

export type Fetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

export class StatusApiError extends Error {
  constructor(
    public readonly path: string,
    public readonly status: number,
  ) {
    super(`Companion request to ${path} failed with HTTP ${status}.`);
    this.name = 'StatusApiError';
  }
}

async function getJson<T>(path: string, fetcher: Fetcher): Promise<T> {
  const response = await fetcher(path, {
    headers: { accept: 'application/json' },
  });

  if (!response.ok) {
    throw new StatusApiError(path, response.status);
  }

  return (await response.json()) as T;
}

export async function loadStatus(fetcher: Fetcher = globalThis.fetch): Promise<StatusSnapshot> {
  const [health, version, capabilities] = await Promise.all([
    getJson<HealthResponse>('/api/health', fetcher),
    getJson<VersionResponse>('/api/version', fetcher),
    getJson<CapabilitiesResponse>('/api/capabilities', fetcher),
  ]);

  return { health, version, capabilities };
}
