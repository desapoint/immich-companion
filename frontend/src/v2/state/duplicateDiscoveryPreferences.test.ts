import { describe, expect, it } from 'vitest';

import {
  DEFAULT_DUPLICATE_DISCOVERY_PREFERENCES,
  DUPLICATE_DISCOVERY_PREFERENCES_KEY,
  readDuplicateDiscoveryPreferences,
  writeDuplicateDiscoveryPreferences,
} from './duplicateDiscoveryPreferences';

function memoryStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
  };
}

describe('duplicate discovery preferences', () => {
  it('restores every setting used for a later discovery run', () => {
    const storage = memoryStorage();
    const selected = { includeExact: false, includeSimilar: true, similarityThreshold: 87.5, validationMode: 'linked' as const, maxCandidates: 24 };

    expect(writeDuplicateDiscoveryPreferences(selected, storage)).toBe(true);
    expect(readDuplicateDiscoveryPreferences(storage)).toEqual(selected);
  });

  it('falls back safely for missing, malformed, or out-of-range saved settings', () => {
    const storage = memoryStorage();
    expect(readDuplicateDiscoveryPreferences(storage)).toEqual(DEFAULT_DUPLICATE_DISCOVERY_PREFERENCES);

    storage.setItem(DUPLICATE_DISCOVERY_PREFERENCES_KEY, '{broken');
    expect(readDuplicateDiscoveryPreferences(storage)).toEqual(DEFAULT_DUPLICATE_DISCOVERY_PREFERENCES);

    storage.setItem(DUPLICATE_DISCOVERY_PREFERENCES_KEY, JSON.stringify({ includeExact: false, includeSimilar: true, similarityThreshold: 200, validationMode: 'unknown', maxCandidates: -1 }));
    expect(readDuplicateDiscoveryPreferences(storage)).toEqual({ ...DEFAULT_DUPLICATE_DISCOVERY_PREFERENCES, includeExact: false });
  });

  it('does not block discovery when browser storage rejects a write', () => {
    const storage = { getItem: () => null, setItem: () => { throw new Error('storage disabled'); } };
    expect(writeDuplicateDiscoveryPreferences(DEFAULT_DUPLICATE_DISCOVERY_PREFERENCES, storage)).toBe(false);
  });
});
