import { afterEach, describe, expect, it, vi } from 'vitest';

import { loadDuplicatePolicy, loadImmichLibraries, loadSyncRuntimeSettings, saveDuplicatePolicy, saveSyncRuntimeSettings } from './settingsApi';

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

describe('duplicate policy API', () => {
  it('loads and saves policy and obtains selectable Immich libraries', async () => {
    const policy = {
      automatic_handling_enabled: true,
      preselect_safe_groups: true,
      exact_file_action: 'resolve' as const,
      keeper_policy: 'prefer_upload' as const,
      analyze_automatically: true,
      verify_upload_streams: false,
      external_library_ids: [],
      similarity_threshold_percent: 95,
    };
    const fetcher = vi.fn<typeof fetch>(async (input) => new Response(JSON.stringify(
      String(input).endsWith('/libraries') ? [] : policy,
    ), { headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetcher);

    await loadDuplicatePolicy();
    await saveDuplicatePolicy(policy);
    await loadImmichLibraries();

    expect(fetcher).toHaveBeenNthCalledWith(1, '/api/settings/duplicates/policy', expect.objectContaining({ headers: expect.any(Object) }));
    expect(fetcher).toHaveBeenNthCalledWith(2, '/api/settings/duplicates/policy', expect.objectContaining({ method: 'PUT', body: JSON.stringify(policy) }));
    expect(fetcher).toHaveBeenNthCalledWith(3, '/api/settings/duplicates/libraries', expect.any(Object));
  });
});
