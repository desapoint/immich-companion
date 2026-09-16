import { afterEach, describe, expect, it, vi } from 'vitest';

import { loadLocalChangeDiagnostics } from './localChangeDiagnostics';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('localized change diagnostics API client', () => {
  it('maps the backend diagnostic grid without changing its values', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      available: true,
      selected_asset_id: 'selected-id',
      reference_asset_id: 'reference-id',
      changed_percent: 18.25,
      localized_changed_percent: 77.5,
      coherent_changed_percent: 14.25,
      largest_changed_region_percent: 9.75,
      substantial_region_count: 3,
      rows: 2,
      columns: 2,
      cells: [[0, 25.5], [84.75, 100]],
      source: 'transcoded',
    }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);
    const controller = new AbortController();

    const diagnostics = await loadLocalChangeDiagnostics(
      'selected-id',
      'reference-id',
      controller.signal,
    );

    expect(diagnostics).toEqual({
      available: true,
      selectedAssetId: 'selected-id',
      referenceAssetId: 'reference-id',
      changedPercent: 18.25,
      localizedChangedPercent: 77.5,
      coherentChangedPercent: 14.25,
      largestChangedRegionPercent: 9.75,
      substantialRegionCount: 3,
      rows: 2,
      columns: 2,
      cells: [[0, 25.5], [84.75, 100]],
      source: 'transcoded',
    });
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v2/duplicates/similarity-local-changes?selected_asset_id=selected-id&reference_asset_id=reference-id');
    expect(init.signal).toBe(controller.signal);
  });

  it('preserves an unavailable cached-evidence response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      available: false,
      selected_asset_id: 'selected-id',
      reference_asset_id: 'reference-id',
      changed_percent: null,
      localized_changed_percent: null,
      coherent_changed_percent: null,
      largest_changed_region_percent: null,
      substantial_region_count: null,
      rows: 0,
      columns: 0,
      cells: [],
      source: null,
    }), { status: 200 })));

    await expect(loadLocalChangeDiagnostics('selected-id', 'reference-id')).resolves.toMatchObject({
      available: false,
      changedPercent: null,
      localizedChangedPercent: null,
      coherentChangedPercent: null,
      largestChangedRegionPercent: null,
      substantialRegionCount: null,
      rows: 0,
      columns: 0,
      cells: [],
      source: null,
    });
  });
});
