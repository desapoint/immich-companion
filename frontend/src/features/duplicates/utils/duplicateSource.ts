import type { DuplicateSource, DuplicateSourceFilter } from '../types/contracts';

export function matchesDuplicateSource(
  sources: readonly DuplicateSource[],
  filter: DuplicateSourceFilter,
): boolean {
  if (filter === 'both') return true;
  return sources.includes(filter === 'immich' ? 'immich_duplicate' : 'companion_similarity');
}

export function duplicateSourceLabels(sources: readonly DuplicateSource[]): string[] {
  return sources.map((source) => source === 'immich_duplicate' ? 'Immich' : 'Similarity');
}
