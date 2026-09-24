import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  clearAllDuplicateResolutionHistory,
  clearDuplicateResolutionHistory,
} from '../api/duplicateResolutionHistory';

function jsonResponse(value: unknown): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('duplicate resolution history helpers', () => {
  it('deletes the selected completed resolution', async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe('/api/assets/duplicates/history/resolution%2Fwith%20spaces');
      expect(init?.method).toBe('DELETE');
      return new Response(null, { status: 204 });
    });
    vi.stubGlobal('fetch', fetchMock);

    await clearDuplicateResolutionHistory('resolution/with spaces');

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('clears all history with one backend request', async () => {
    const fetcher = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      expect(String(input)).toBe('/api/assets/duplicates/history');
      expect(init?.method).toBe('DELETE');
      return jsonResponse({ cleared: 237 });
    });
    vi.stubGlobal('fetch', fetcher);

    await expect(clearAllDuplicateResolutionHistory()).resolves.toBe(237);
    expect(fetcher).toHaveBeenCalledTimes(1);
  });
});
