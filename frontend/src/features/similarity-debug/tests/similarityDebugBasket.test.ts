import { describe, expect, it } from 'vitest';

import {
  SIMILARITY_DEBUG_STORAGE_KEY,
  addSimilarityDebugAssets,
  clearSimilarityDebugAssets,
  readSimilarityDebugAssets,
  removeSimilarityDebugAsset,
} from '../state/similarityDebugBasket';

function memoryStorage() {
  const values = new Map<string, string>();
  return {
    values,
    storage: {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    },
  };
}

describe('similarity debug basket', () => {
  it('deduplicates assets and persists insertion order', () => {
    const { storage, values } = memoryStorage();

    expect(addSimilarityDebugAssets(['a', 'b', 'a'], storage)).toBe(2);
    expect(addSimilarityDebugAssets(['b', 'c'], storage)).toBe(1);
    expect(readSimilarityDebugAssets(storage)).toEqual(['a', 'b', 'c']);
    expect(values.get(SIMILARITY_DEBUG_STORAGE_KEY)).toBe(JSON.stringify(['a', 'b', 'c']));
  });

  it('removes and clears persisted assets', () => {
    const { storage } = memoryStorage();
    addSimilarityDebugAssets(['a', 'b', 'c'], storage);

    removeSimilarityDebugAsset('b', storage);
    expect(readSimilarityDebugAssets(storage)).toEqual(['a', 'c']);

    clearSimilarityDebugAssets(storage);
    expect(readSimilarityDebugAssets(storage)).toEqual([]);
  });

  it('caps the debug basket so arbitrary comparisons stay bounded', () => {
    const { storage } = memoryStorage();
    const ids = Array.from({ length: 20 }, (_, index) => `asset-${index}`);

    expect(addSimilarityDebugAssets(ids, storage)).toBe(12);
    expect(readSimilarityDebugAssets(storage)).toEqual(ids.slice(0, 12));
  });
});
