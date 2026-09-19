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
      validation_mode: 'linked',
      max_link_depth: 3,
      max_candidates: 16,
    }));
    vi.stubGlobal('fetch', fetcher);

    await expect(duplicateDiscoverySettingsRepository.load()).resolves.toEqual({
      includeExact: false,
      includeSimilar: true,
      similarityThreshold: 92.5,
      validationMode: 'linked',
      maxLinkDepth: 3,
      maxCandidates: 16,
    });
    expect(fetcher).toHaveBeenCalledWith(
      '/api/settings/duplicates/discovery',
      expect.objectContaining({ signal: undefined }),
    );
  });

  it('defaults older settings responses to a depth limit of two', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => response({
      include_exact: true,
      include_similar: true,
      similarity_threshold: 95,
      validation_mode: 'linked',
      max_candidates: 8,
    })));

    await expect(duplicateDiscoverySettingsRepository.load()).resolves.toMatchObject({
      maxLinkDepth: 2,
    });
  });

  it('persists the complete discovery configuration', async () => {
    const fetcher = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      expect(init?.method).toBe('PUT');
      expect(JSON.parse(String(init?.body))).toEqual({
        include_exact: true,
        include_similar: true,
        similarity_threshold: 97,
        validation_mode: 'strict',
        max_link_depth: 2,
        max_candidates: 12,
      });
      return response({
        include_exact: true,
        include_similar: true,
        similarity_threshold: 97,
        validation_mode: 'strict',
        max_link_depth: 2,
        max_candidates: 12,
      });
    });
    vi.stubGlobal('fetch', fetcher);

    await expect(duplicateDiscoverySettingsRepository.save({
      includeExact: true,
      includeSimilar: true,
      similarityThreshold: 97,
      validationMode: 'strict',
      maxLinkDepth: 2,
      maxCandidates: 12,
    })).resolves.toMatchObject({
      similarityThreshold: 97,
      maxLinkDepth: 2,
      maxCandidates: 12,
    });
  });
});
