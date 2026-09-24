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
  comparisonMaxZoomPercent: 0,
};

describe('duplicate comparison diagnostics cache', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    loadAlignmentSettings.mockResolvedValue({ maxDisplacementPercent: 10, maxRotationDegrees: 0, maxZoomPercent: 0 });
    loadDiagnostics.mockResolvedValue(result);
  });

  it('recomputes the same pair after another client changes alignment settings', async () => {
    loadAlignmentSettings
      .mockResolvedValueOnce({ maxDisplacementPercent: 10, maxRotationDegrees: 0, maxZoomPercent: 0 })
      .mockResolvedValueOnce({ maxDisplacementPercent: 15, maxRotationDegrees: 0, maxZoomPercent: 0 })
      .mockResolvedValueOnce({ maxDisplacementPercent: 15, maxRotationDegrees: 0, maxZoomPercent: 0 });
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
      { maxDisplacementPercent: 10, maxRotationDegrees: 0, maxZoomPercent: 0 },
    );
    expect(loadDiagnostics).toHaveBeenNthCalledWith(
      2,
      selected.id,
      reference.id,
      expect.any(AbortSignal),
      { maxDisplacementPercent: 15, maxRotationDegrees: 0, maxZoomPercent: 0 },
    );
  });

  it('caches under the exact settings identity returned by diagnostics', async () => {
    const resultForCurrentSettings = {
      ...result,
      comparisonMaxDisplacementPercent: 15,
      comparisonMaxRotationDegrees: 2,
      comparisonMaxZoomPercent: 12,
    };
    loadAlignmentSettings.mockResolvedValue({ maxDisplacementPercent: 15, maxRotationDegrees: 2, maxZoomPercent: 12 });
    loadDiagnostics.mockResolvedValue(resultForCurrentSettings);
    const controller = new DuplicateComparisonDataController();

    await controller.loadDiagnostics(selected, reference, true);
    await controller.loadDiagnostics(selected, reference, true);

    expect(loadDiagnostics).toHaveBeenCalledTimes(1);
    expect(controller.localDiagnostics).toEqual(resultForCurrentSettings);
  });

  it('drops cached diagnostics when the viewer lifecycle is invalidated', async () => {
    const controller = new DuplicateComparisonDataController();

    await controller.loadDiagnostics(selected, reference, true);
    controller.invalidateDiagnostics();
    await controller.loadDiagnostics(selected, reference, true);

    expect(loadDiagnostics).toHaveBeenCalledTimes(2);
  });

  it('aborts a superseded diagnostics request', async () => {
    let firstSignal: AbortSignal | undefined;
    loadAlignmentSettings
      .mockImplementationOnce((signal: AbortSignal) => new Promise((_resolve, reject) => {
        firstSignal = signal;
        signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      }))
      .mockResolvedValueOnce({ maxDisplacementPercent: 10, maxRotationDegrees: 0, maxZoomPercent: 0 });
    const controller = new DuplicateComparisonDataController();

    const first = controller.loadDiagnostics(selected, reference, true);
    await vi.waitFor(() => expect(firstSignal).toBeDefined());
    const second = controller.loadDiagnostics(selected, reference, true);
    await Promise.all([first, second]);

    expect(firstSignal?.aborted).toBe(true);
    expect(loadDiagnostics).toHaveBeenCalledTimes(1);
    expect(controller.localDiagnostics).toEqual(result);
  });
});
