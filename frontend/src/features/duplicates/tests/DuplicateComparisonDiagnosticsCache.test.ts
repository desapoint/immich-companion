import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { AssetRecord } from '../types/contracts';

const { loadDiagnostics, loadAlignmentSettings } = vi.hoisted(() => ({
  loadDiagnostics: vi.fn(),
  loadAlignmentSettings: vi.fn(),
}));

vi.mock('../utils/localChangeDiagnostics', () => ({
  loadLocalChangeDiagnostics: loadDiagnostics,
}));

vi.mock('../api/comparisonAlignmentSettingsRepository', () => ({
  comparisonAlignmentSettingsRepository: { load: loadAlignmentSettings },
}));

import { DuplicateComparisonDataController } from '../state/duplicateComparisonData.svelte';

const selected = { id: 'selected', asset_type: 'IMAGE' } as AssetRecord;
const reference = { id: 'reference', asset_type: 'IMAGE' } as AssetRecord;
const result = {
  available: true,
  selectedAssetId: selected.id,
  referenceAssetId: reference.id,
  changedPercent: 2,
  localizedChangedPercent: 3,
  rows: 1,
  columns: 1,
  cells: [[2]],
  source: 'original' as const,
  comparisonMaxDisplacementPercent: 10,
  comparisonMaxRotationDegrees: 0,
};

describe('duplicate comparison diagnostics cache', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadDiagnostics.mockResolvedValue(result);
  });

  it('recomputes the same pair after another client changes alignment settings', async () => {
    loadAlignmentSettings
      .mockResolvedValueOnce({ maxDisplacementPercent: 10, maxRotationDegrees: 0 })
      .mockResolvedValueOnce({ maxDisplacementPercent: 15, maxRotationDegrees: 0 })
      .mockResolvedValueOnce({ maxDisplacementPercent: 15, maxRotationDegrees: 0 });
    loadDiagnostics
      .mockResolvedValueOnce(result)
      .mockResolvedValueOnce({
        ...result,
        comparisonMaxDisplacementPercent: 15,
        comparisonMaxRotationDegrees: 0,
      });
    const controller = new DuplicateComparisonDataController();

    await controller.loadDiagnostics(selected, reference, true);
    await controller.loadDiagnostics(selected, reference, true);
    await controller.loadDiagnostics(selected, reference, true);

    expect(loadAlignmentSettings).toHaveBeenCalledTimes(3);
    expect(loadDiagnostics).toHaveBeenCalledTimes(2);
    expect(loadDiagnostics).toHaveBeenNthCalledWith(
      1,
      selected.id,
      reference.id,
      expect.any(AbortSignal),
      { maxDisplacementPercent: 10, maxRotationDegrees: 0 },
    );
    expect(loadDiagnostics).toHaveBeenNthCalledWith(
      2,
      selected.id,
      reference.id,
      expect.any(AbortSignal),
      { maxDisplacementPercent: 15, maxRotationDegrees: 0 },
    );
  });

  it('caches under the exact settings identity returned by diagnostics', async () => {
    const resultForCurrentSettings = {
      ...result,
      comparisonMaxDisplacementPercent: 15,
      comparisonMaxRotationDegrees: 2,
    };
    loadAlignmentSettings.mockResolvedValue({ maxDisplacementPercent: 15, maxRotationDegrees: 2 });
    loadDiagnostics.mockResolvedValue(resultForCurrentSettings);
    const controller = new DuplicateComparisonDataController();

    await controller.loadDiagnostics(selected, reference, true);
    await controller.loadDiagnostics(selected, reference, true);

    expect(loadDiagnostics).toHaveBeenCalledTimes(1);
    expect(controller.localDiagnostics).toEqual(resultForCurrentSettings);
  });
});
