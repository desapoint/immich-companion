import { describe, expect, it } from 'vitest';

import {
  V2_ASSET_FILTER_HANDOFF_KEY,
  V2_DEFAULT_PAGE,
  V2_PAGE_KEYS,
  consumeV2AssetFilterHandoff,
  storeV2AssetFilterHandoff,
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

  it('falls back safely for unknown and nested page paths', () => {
    expect(v2PageFromPath('/v2/unknown')).toBe(V2_DEFAULT_PAGE);
    expect(v2PageFromPath('/v2/assets/unexpected')).toBe(V2_DEFAULT_PAGE);
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
