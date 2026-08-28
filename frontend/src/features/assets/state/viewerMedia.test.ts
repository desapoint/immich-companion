import { describe, expect, it } from 'vitest';

import { buildViewerMediaUrls, isHeicMimeType } from './viewerMedia';

describe('viewer media fallback selection', () => {
  it('uses original then fullsize then preview for browser-compatible media', () => {
    expect(buildViewerMediaUrls('asset id', 'image/jpeg', true)).toEqual([
      '/api/assets/asset%20id/original',
      '/api/assets/asset%20id/thumbnail?size=fullsize',
      '/api/assets/asset%20id/thumbnail?size=preview',
    ]);
  });

  it('keeps the original first when the HEIC decode probe succeeds', () => {
    expect(buildViewerMediaUrls('asset', 'image/heic', true)).toEqual([
      '/api/assets/asset/original',
      '/api/assets/asset/thumbnail?size=fullsize',
      '/api/assets/asset/thumbnail?size=preview',
    ]);
  });

  it('skips an undecodable HEIC original and falls back through Immich derivatives', () => {
    expect(buildViewerMediaUrls('asset', 'image/heif', false)).toEqual([
      '/api/assets/asset/thumbnail?size=fullsize',
      '/api/assets/asset/thumbnail?size=preview',
    ]);
  });

  it('recognizes HEIC and HEIF MIME types case-insensitively', () => {
    expect(isHeicMimeType('image/heic')).toBe(true);
    expect(isHeicMimeType('IMAGE/HEIF')).toBe(true);
    expect(isHeicMimeType('image/jpeg')).toBe(false);
    expect(isHeicMimeType(null)).toBe(false);
  });
});
