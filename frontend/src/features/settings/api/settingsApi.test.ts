import { afterEach, describe, expect, it, vi } from 'vitest';

import { loadSyncRuntimeSettings, saveSyncRuntimeSettings } from './settingsApi';

afterEach(() => vi.unstubAllGlobals());

describe('global sync runtime settings API', () => {
  it('loads and saves persisted global-sync pacing', async () => {
    const fetcher = vi.fn<typeof fetch>(async () => new Response(JSON.stringify({
      full_batch_size: 50,
      full_min_batch_delay_seconds: 0.2,
    }), { headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetcher);

    await loadSyncRuntimeSettings();
    await saveSyncRuntimeSettings({ full_batch_size: 25, full_min_batch_delay_seconds: 0.5 });

    expect(fetcher).toHaveBeenNthCalledWith(1, '/api/settings/sync/runtime', expect.objectContaining({ method: 'GET' }));
    expect(fetcher).toHaveBeenNthCalledWith(2, '/api/settings/sync/runtime', expect.objectContaining({
      method: 'PUT', body: '{"full_batch_size":25,"full_min_batch_delay_seconds":0.5}',
    }));
  });
});
