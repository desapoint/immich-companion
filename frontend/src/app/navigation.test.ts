import { describe, expect, it } from 'vitest';

import {
  ASSET_FILTER_HANDOFF_KEY,
  DEFAULT_PAGE,
  PAGE_KEYS,
  consumeAssetFilterHandoff,
  legacyV2RedirectPath,
  storeAssetFilterHandoff,
  assetIdFromPath,
  assetViewerPath,
  pageFromLegacyHash,
  pageFromPath,
  pagePath,
} from './navigation';

describe('V2 navigation paths', () => {
  it.each(PAGE_KEYS)('maps %s to and from its canonical URL', (key) => {
    const path = key === 'status' ? '/' : `/${key}`;
    expect(pagePath(key)).toBe(path);
    expect(pageFromPath(path)).toBe(key);
    expect(pageFromPath(`${path}/`)).toBe(key);
  });

  it('uses the canonical root for the status page', () => {
    expect(pageFromPath('/')).toBe(DEFAULT_PAGE);
    expect(pageFromPath('///')).toBe(DEFAULT_PAGE);
  });

  it('supports direct asset viewer URLs while keeping Assets as the active page', () => {
    const assetId = '11111111-2222-4333-8444-555555555555';
    const path = assetViewerPath(assetId);
    expect(path).toBe(`/assets/${assetId}`);
    expect(assetIdFromPath(path)).toBe(assetId);
    expect(assetIdFromPath(`${path}/`)).toBe(assetId);
    expect(pageFromPath(path)).toBe('assets');
  });

  it('encodes and decodes asset ids safely', () => {
    const assetId = 'asset id/with?reserved#characters';
    const path = assetViewerPath(assetId);
    expect(path).toBe('/assets/asset%20id%2Fwith%3Freserved%23characters');
    expect(assetIdFromPath(path)).toBe(assetId);
  });

  it('falls back safely for unknown and unsupported nested page paths', () => {
    expect(pageFromPath('/unknown')).toBe(DEFAULT_PAGE);
    expect(pageFromPath('/assets/one/two')).toBe(DEFAULT_PAGE);
    expect(assetIdFromPath('/assets/%E0%A4%A')).toBeNull();
  });

  it('redirects old V2 frontend paths to canonical paths', () => {
    expect(legacyV2RedirectPath('/v2')).toBe('/');
    expect(legacyV2RedirectPath('/v2/')).toBe('/');
    expect(legacyV2RedirectPath('/v2/assets/asset%2Fid')).toBe('/assets/asset%2Fid');
    expect(legacyV2RedirectPath('/v2/settings')).toBe('/settings');
    expect(legacyV2RedirectPath('/v2/unknown')).toBe('/');
    expect(legacyV2RedirectPath('/api/v2/assets')).toBeNull();
  });

  it('recognizes valid legacy hash links for migration', () => {
    expect(pageFromLegacyHash('#duplicates')).toBe('duplicates');
    expect(pageFromLegacyHash('assets')).toBe('assets');
    expect(pageFromLegacyHash('#unknown')).toBeNull();
    expect(pageFromLegacyHash('')).toBeNull();
  });

  it('stores and consumes an asset filter handoff once', () => {
    const values = new Map<string, string>();
    const storage = {
      setItem: (key: string, value: string) => values.set(key, value),
      getItem: (key: string) => values.get(key) ?? null,
      removeItem: (key: string) => values.delete(key),
    };

    storeAssetFilterHandoff({ albumIds: ['album-1'], tagIds: ['tag-1', 'tag-2'] }, storage);
    expect(values.has(ASSET_FILTER_HANDOFF_KEY)).toBe(true);
    expect(consumeAssetFilterHandoff(storage)).toEqual({ albumIds: ['album-1'], tagIds: ['tag-1', 'tag-2'] });
    expect(consumeAssetFilterHandoff(storage)).toBeNull();
  });
});
