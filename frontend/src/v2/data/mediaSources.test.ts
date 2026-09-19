import { describe, expect, it } from 'vitest';
import type { MediaResource } from './contracts';
import { mediaResourceSources, nextMediaSourceIndex } from './mediaSources';

const resource: MediaResource = {
  url: '/decoded/asset',
  fallbackUrls: ['/original/asset', '/preview/asset', '/decoded/asset'],
  mimeType: 'image/jpeg',
  posterUrl: null,
  delivery: 'decoded',
  originalMimeType: 'image/heic',
  expiresAt: null,
};

describe('media source fallback', () => {
  it('keeps the viewer order while removing duplicate URLs', () => {
    expect(mediaResourceSources(resource)).toEqual([
      '/decoded/asset',
      '/original/asset',
      '/preview/asset',
    ]);
  });

  it('advances until the final source is exhausted', () => {
    expect(nextMediaSourceIndex(0, 3)).toBe(1);
    expect(nextMediaSourceIndex(1, 3)).toBe(2);
    expect(nextMediaSourceIndex(2, 3)).toBeNull();
  });
});
