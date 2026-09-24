import { afterEach, describe, expect, it, vi } from 'vitest';

import { duplicateDiscoverySettingsRepository } from '../api/duplicateDiscoverySettingsRepository';

function response(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('duplicate discovery settings repository', () => {
  it('loads persisted discovery settings from Companion', async () => {
    const fetcher = vi.fn(async () => response({
      include_exact: false,
      include_similar: true,
      similarity_threshold: 92.5,
      maximum_perceptual_distance: 14,
      comparison_max_displacement_percent: 12,
      comparison_max_rotation_degrees: 3,
      validation_mode: 'linked',
      max_link_depth: 3,
      max_candidates: 16,
      maximum_matches: 12000,
    }));
    vi.stubGlobal('fetch', fetcher);

    await expect(duplicateDiscoverySettingsRepository.load()).resolves.toEqual({
      includeExact: false,
      includeSimilar: true,
      similarityThreshold: 92.5,
      maximumPerceptualDistance: 14,
      comparisonMaxDisplacementPercent: 12,
      comparisonMaxRotationDegrees: 3,
      validationMode: 'linked',
      maxLinkDepth: 3,
      maxCandidates: 16,
      maximumMatches: 12000,
    });
    expect(fetcher).toHaveBeenCalledWith(
      '/api/settings/duplicates/discovery',
      expect.objectContaining({ signal: undefined }),
    );
  });

  it('defaults fields missing from older settings responses', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({
      include_exact: true,
      include_similar: true,
      similarity_threshold: 95,
      validation_mode: 'linked',
      max_candidates: 8,
    })));

    await expect(duplicateDiscoverySettingsRepository.load()).resolves.toMatchObject({
      maxLinkDepth: 2,
      maximumPerceptualDistance: 12,
      maximumMatches: 5000,
      comparisonMaxDisplacementPercent: 10,
      comparisonMaxRotationDegrees: 0,
    });
  });

  it('persists the complete discovery configuration', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe('PUT');
      expect(JSON.parse(String(init?.body))).toEqual({
        include_exact: true,
        include_similar: true,
        similarity_threshold: 97,
        maximum_perceptual_distance: 14,
        comparison_max_displacement_percent: 11,
        comparison_max_rotation_degrees: 2,
        validation_mode: 'strict',
        max_link_depth: 2,
        max_candidates: 12,
        maximum_matches: 15000,
      });
      return response({
        include_exact: true,
        include_similar: true,
        similarity_threshold: 97,
        maximum_perceptual_distance: 14,
        comparison_max_displacement_percent: 11,
        comparison_max_rotation_degrees: 2,
        validation_mode: 'strict',
        max_link_depth: 2,
        max_candidates: 12,
        maximum_matches: 15000,
      });
    });
    vi.stubGlobal('fetch', fetcher);

    await expect(duplicateDiscoverySettingsRepository.save({
      includeExact: true,
      includeSimilar: true,
      similarityThreshold: 97,
      maximumPerceptualDistance: 14,
      comparisonMaxDisplacementPercent: 11,
      comparisonMaxRotationDegrees: 2,
      validationMode: 'strict',
      maxLinkDepth: 2,
      maxCandidates: 12,
      maximumMatches: 15000,
    })).resolves.toMatchObject({
      similarityThreshold: 97,
      maximumPerceptualDistance: 14,
      maxLinkDepth: 2,
      maxCandidates: 12,
      maximumMatches: 15000,
    });
  });

  it('patches discovery-only values without sending alignment settings', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe('PATCH');
      expect(JSON.parse(String(init?.body))).toEqual({
        include_exact: true,
        include_similar: false,
        similarity_threshold: 91,
        maximum_perceptual_distance: 15,
        validation_mode: 'strict',
        max_link_depth: 2,
        max_candidates: 8,
        maximum_matches: 5000,
      });
      return response({
        include_exact: true,
        include_similar: false,
        similarity_threshold: 91,
        maximum_perceptual_distance: 15,
        comparison_max_displacement_percent: 17,
        comparison_max_rotation_degrees: 4,
        validation_mode: 'strict',
        max_link_depth: 2,
        max_candidates: 8,
        maximum_matches: 5000,
      });
    });
    vi.stubGlobal('fetch', fetcher);

    await expect(duplicateDiscoverySettingsRepository.patchDiscovery({
      includeExact: true,
      includeSimilar: false,
      similarityThreshold: 91,
      maximumPerceptualDistance: 15,
      validationMode: 'strict',
      maxLinkDepth: 2,
      maxCandidates: 8,
      maximumMatches: 5000,
    })).resolves.toMatchObject({
      comparisonMaxDisplacementPercent: 17,
      comparisonMaxRotationDegrees: 4,
    });
  });
});
