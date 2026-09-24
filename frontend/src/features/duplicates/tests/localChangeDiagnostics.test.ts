import { afterEach, describe, expect, it, vi } from 'vitest';

import { loadLocalChangeDiagnostics } from '../utils/localChangeDiagnostics';

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
      aligned_changed_percent: 6.5,
      raw_similarity_percent: 88.4,
      aligned_similarity_percent: 97.2,
      alignment_applied: true,
      alignment_shift_percent: 3.12,
      alignment_rotation_degrees: -2,
      alignment_overlap_percent: 94.2,
      comparison_max_displacement_percent: 15,
      comparison_max_rotation_degrees: 3,
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
      alignedChangedPercent: 6.5,
      rawSimilarityPercent: 88.4,
      alignedSimilarityPercent: 97.2,
      alignmentApplied: true,
      alignmentShiftPercent: 3.12,
      alignmentRotationDegrees: -2,
      alignmentOverlapPercent: 94.2,
      comparisonMaxDisplacementPercent: 15,
      comparisonMaxRotationDegrees: 3,
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
      aligned_changed_percent: null,
      raw_similarity_percent: null,
      aligned_similarity_percent: null,
      alignment_applied: false,
      alignment_shift_percent: null,
      alignment_overlap_percent: null,
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
      alignedChangedPercent: null,
      rawSimilarityPercent: null,
      alignedSimilarityPercent: null,
      alignmentApplied: false,
      alignmentShiftPercent: null,
      alignmentOverlapPercent: null,
      rows: 0,
      columns: 0,
      cells: [],
      source: null,
    });
  });

  it('sends and returns the exact comparison settings used for diagnostics', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      available: false,
      selected_asset_id: 'selected-id',
      reference_asset_id: 'reference-id',
      changed_percent: null,
      localized_changed_percent: null,
      rows: 0,
      columns: 0,
      cells: [],
      source: null,
      comparison_max_displacement_percent: 14,
      comparison_max_rotation_degrees: 2,
    }), { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    const diagnostics = await loadLocalChangeDiagnostics('selected-id', 'reference-id', undefined, {
      maxDisplacementPercent: 14,
      maxRotationDegrees: 2,
    });

    expect(fetchMock.mock.calls[0]?.[0]).toContain('comparison_max_displacement_percent=14');
    expect(fetchMock.mock.calls[0]?.[0]).toContain('comparison_max_rotation_degrees=2');
    expect(diagnostics.comparisonMaxDisplacementPercent).toBe(14);
    expect(diagnostics.comparisonMaxRotationDegrees).toBe(2);
  });
});
