import { afterEach, describe, expect, it, vi } from 'vitest';

import { duplicateDiscoverySettingsRepository } from './duplicateDiscoverySettingsRepository';

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
      validation_mode: 'linked',
      max_candidates: 16,
    }));
    vi.stubGlobal('fetch', fetcher);

    await expect(duplicateDiscoverySettingsRepository.load()).resolves.toEqual({
      includeExact: false,
      includeSimilar: true,
      similarityThreshold: 92.5,
      validationMode: 'linked',
      maxCandidates: 16,
    });
    expect(fetcher).toHaveBeenCalledWith(
      '/api/settings/duplicates/discovery',
      expect.objectContaining({ signal: undefined }),
    );
  });

  it('persists the complete discovery configuration', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe('PUT');
      expect(JSON.parse(String(init?.body))).toEqual({
        include_exact: true,
        include_similar: true,
        similarity_threshold: 97,
        validation_mode: 'strict',
        max_candidates: 12,
      });
      return response({
        include_exact: true,
        include_similar: true,
        similarity_threshold: 97,
        validation_mode: 'strict',
        max_candidates: 12,
      });
    });
    vi.stubGlobal('fetch', fetcher);

    await expect(duplicateDiscoverySettingsRepository.save({
      includeExact: true,
      includeSimilar: true,
      similarityThreshold: 97,
      validationMode: 'strict',
      maxCandidates: 12,
    })).resolves.toMatchObject({
      similarityThreshold: 97,
      maxCandidates: 12,
    });
  });
});
