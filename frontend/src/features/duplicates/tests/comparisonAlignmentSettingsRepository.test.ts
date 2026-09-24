import { afterEach, describe, expect, it, vi } from 'vitest';

import { comparisonAlignmentSettingsRepository } from '../api/comparisonAlignmentSettingsRepository';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('comparison alignment settings repository', () => {
  it('loads the server settings used as the diagnostics cache identity', async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({
      comparison_max_displacement_percent: 14,
      comparison_max_rotation_degrees: 2,
    }), { status: 200, headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetcher);

    await expect(comparisonAlignmentSettingsRepository.load()).resolves.toEqual({
      maxDisplacementPercent: 14,
      maxRotationDegrees: 2,
    });
    expect(fetcher).toHaveBeenCalledWith(
      '/api/settings/duplicates/comparison-alignment',
      expect.objectContaining({ signal: undefined }),
    );
  });

  it('updates only the comparison settings', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe('PUT');
      expect(JSON.parse(String(init?.body))).toEqual({
        comparison_max_displacement_percent: 15,
        comparison_max_rotation_degrees: 3,
      });
      return new Response(JSON.stringify({
        comparison_max_displacement_percent: 15,
        comparison_max_rotation_degrees: 3,
      }), { status: 200, headers: { 'content-type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetcher);

    await expect(comparisonAlignmentSettingsRepository.save({
      maxDisplacementPercent: 15,
      maxRotationDegrees: 3,
    })).resolves.toEqual({ maxDisplacementPercent: 15, maxRotationDegrees: 3 });
  });
});
