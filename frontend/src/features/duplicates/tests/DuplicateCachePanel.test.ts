import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import type { SimilarityCacheStatus } from '../types/contracts';
import DuplicateCachePanel from '../components/DuplicateCachePanel.svelte';

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

describe('DuplicateCachePanel', () => {
  it('keeps disposable cache controls separate from evidence generation', () => {
    const { body } = render(DuplicateCachePanel, {
      props: {
        status,
        onrefresh: () => {},
        onclear: () => {},
      },
    });

    expect(body).toContain('Disposable similarity cache');
    expect(body).toContain('Clear pair results');
    expect(body).toContain('do not advance the evidence epoch');
    expect(body).not.toContain('Start new evidence epoch');
  });

  it('still exposes cache refresh when telemetry is unavailable', () => {
    const { body } = render(DuplicateCachePanel, {
      props: {
        status: null,
        onrefresh: () => {},
        onclear: () => {},
      },
    });

    expect(body).toContain('Cache telemetry is unavailable');
    expect(body).toContain('Evidence-epoch controls remain available separately');
    expect(body).toContain('Refresh cache status');
  });
});
