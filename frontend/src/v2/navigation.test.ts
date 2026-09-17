import { describe, expect, it } from 'vitest';

import {
  V2_ASSET_FILTER_HANDOFF_KEY,
  V2_DEFAULT_PAGE,
  V2_PAGE_KEYS,
  consumeV2AssetFilterHandoff,
  storeV2AssetFilterHandoff,
  v2AssetIdFromPath,
  v2AssetViewerPath,
  v2PageFromLegacyHash,
  v2PageFromPath,
  v2PagePath,
} from './navigation';

describe('V2 navigation paths', () => {
  it.each(V2_PAGE_KEYS)('maps %s to and from its canonical URL', (key) => {
    const path = `/v2/${key}`;
    expect(v2PagePath(key)).toBe(path);
    expect(v2PageFromPath(path)).toBe(key);
    expect(v2PageFromPath(`${path}/`)).toBe(key);
  });

  it('keeps the V2 root as a settings alias', () => {
    expect(v2PageFromPath('/v2')).toBe(V2_DEFAULT_PAGE);
    expect(v2PageFromPath('/v2/')).toBe(V2_DEFAULT_PAGE);
  });

  it('supports direct asset viewer URLs while keeping Assets as the active page', () => {
    const assetId = '11111111-2222-4333-8444-555555555555';
    const path = v2AssetViewerPath(assetId);
    expect(path).toBe(`/v2/assets/${assetId}`);
    expect(v2AssetIdFromPath(path)).toBe(assetId);
    expect(v2AssetIdFromPath(`${path}/`)).toBe(assetId);
    expect(v2PageFromPath(path)).toBe('assets');
  });

  it('encodes and decodes asset ids safely', () => {
    const assetId = 'asset id/with?reserved#characters';
    const path = v2AssetViewerPath(assetId);
    expect(path).toBe('/v2/assets/asset%20id%2Fwith%3Freserved%23characters');
    expect(v2AssetIdFromPath(path)).toBe(assetId);
  });

  it('falls back safely for unknown and unsupported nested page paths', () => {
    expect(v2PageFromPath('/v2/unknown')).toBe(V2_DEFAULT_PAGE);
    expect(v2PageFromPath('/v2/assets/one/two')).toBe(V2_DEFAULT_PAGE);
    expect(v2AssetIdFromPath('/v2/assets/%E0%A4%A')).toBeNull();
  });

  it('recognizes valid legacy hash links for migration', () => {
    expect(v2PageFromLegacyHash('#duplicates')).toBe('duplicates');
    expect(v2PageFromLegacyHash('assets')).toBe('assets');
    expect(v2PageFromLegacyHash('#unknown')).toBeNull();
    expect(v2PageFromLegacyHash('')).toBeNull();
  });

  it('stores and consumes an asset filter handoff once', () => {
    const values = new Map<string, string>();
    const storage = {
      setItem: (key: string, value: string) => values.set(key, value),
      getItem: (key: string) => values.get(key) ?? null,
      removeItem: (key: string) => values.delete(key),
    };

    storeV2AssetFilterHandoff({ albumIds: ['album-1'], tagIds: ['tag-1', 'tag-2'] }, storage);
    expect(values.has(V2_ASSET_FILTER_HANDOFF_KEY)).toBe(true);
    expect(consumeV2AssetFilterHandoff(storage)).toEqual({ albumIds: ['album-1'], tagIds: ['tag-1', 'tag-2'] });
    expect(consumeV2AssetFilterHandoff(storage)).toBeNull();
  });
});
