import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import type { SimilarityCacheStatus } from '../data/contracts';
import V2DuplicateCachePanel from './V2DuplicateCachePanel.svelte';

const disk = {
  path: '/tmp/cache',
  healthy: true,
  usedBytes: 0,
  maxBytes: 1024,
  freeBytes: 1024,
  entryCount: 0,
  hits: 0,
  misses: 0,
  evictions: 0,
  cleanupFailures: 0,
};

const status: SimilarityCacheStatus = {
  configFingerprint: '0123456789abcdef',
  featureCount: 12,
  featureEstimatedBytes: 12_000,
  pairCount: 3,
  pairEstimatedBytes: 1_536,
  pairMaxBytes: 20_000,
  pairHits: 2,
  pairMisses: 1,
  pairEvictions: 0,
  hotCount: 2,
  hotEstimatedBytes: 2_048,
  hotMaxBytes: 10_000,
  hotHits: 1,
  hotMisses: 1,
  hotEvictions: 0,
  referenceLatencyP50Ms: 3,
  referenceLatencyP95Ms: 8,
  previews: disk,
  decode: disk,
  generatedAt: '2026-09-17T18:00:00Z',
};

describe('V2DuplicateCachePanel', () => {
  it('exposes the destructive evidence rebuild separately from disposable cache clearing', () => {
    const { body } = render(V2DuplicateCachePanel, {
      props: {
        status,
        onrefresh: () => {},
        onclear: () => {},
      },
    });

    expect(body).toContain('Similarity evidence generation');
    expect(body).toContain('Rebuild similarity evidence');
    expect(body).toContain('hard boundary for search fingerprints');
    expect(body).toContain('Review decisions and resolution history are preserved.');
    expect(body).toContain('Clear pair results');
    expect(body).toContain('Clearing disposable previews or pair results does not remove durable Appearance features');
  });
});
