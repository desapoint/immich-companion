import type { SimilarityValidationMode } from '../data/contracts';

export const DUPLICATE_DISCOVERY_PREFERENCES_KEY = 'immich-companion:v2:duplicate-discovery-settings:v1';

export interface DuplicateDiscoveryPreferences {
  includeExact: boolean;
  includeSimilar: boolean;
  similarityThreshold: number;
  validationMode: SimilarityValidationMode;
  maxCandidates: number;
}

export const DEFAULT_DUPLICATE_DISCOVERY_PREFERENCES: DuplicateDiscoveryPreferences = {
  includeExact: true,
  includeSimilar: true,
  similarityThreshold: 95,
  validationMode: 'strict',
  maxCandidates: 8,
};

type PreferenceStorage = Pick<Storage, 'getItem' | 'setItem'>;

function browserStorage(): PreferenceStorage | null {
  return typeof localStorage === 'undefined' ? null : localStorage;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function readDuplicateDiscoveryPreferences(storage?: PreferenceStorage): DuplicateDiscoveryPreferences {
  try {
    const raw = (storage ?? browserStorage())?.getItem(DUPLICATE_DISCOVERY_PREFERENCES_KEY);
    if (!raw) return { ...DEFAULT_DUPLICATE_DISCOVERY_PREFERENCES };
    const saved: unknown = JSON.parse(raw);
    if (!isRecord(saved)) return { ...DEFAULT_DUPLICATE_DISCOVERY_PREFERENCES };
    return {
      includeExact: typeof saved.includeExact === 'boolean' ? saved.includeExact : true,
      includeSimilar: typeof saved.includeSimilar === 'boolean' ? saved.includeSimilar : true,
      similarityThreshold: typeof saved.similarityThreshold === 'number' && Number.isFinite(saved.similarityThreshold) && saved.similarityThreshold >= 50 && saved.similarityThreshold <= 100 ? saved.similarityThreshold : 95,
      validationMode: saved.validationMode === 'reference' || saved.validationMode === 'linked' || saved.validationMode === 'strict' ? saved.validationMode : 'strict',
      maxCandidates: typeof saved.maxCandidates === 'number' && Number.isInteger(saved.maxCandidates) && saved.maxCandidates >= 1 && saved.maxCandidates <= 64 ? saved.maxCandidates : 8,
    };
  } catch {
    return { ...DEFAULT_DUPLICATE_DISCOVERY_PREFERENCES };
  }
}

export function writeDuplicateDiscoveryPreferences(value: DuplicateDiscoveryPreferences, storage?: PreferenceStorage): boolean {
  try {
    const target = storage ?? browserStorage();
    if (!target) return false;
    target.setItem(DUPLICATE_DISCOVERY_PREFERENCES_KEY, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}
