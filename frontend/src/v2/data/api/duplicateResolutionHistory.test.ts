import { afterEach, describe, expect, it, vi } from 'vitest';

import { clearDuplicateResolutionHistory } from './duplicateResolutionHistory';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('clearDuplicateResolutionHistory', () => {
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
});
