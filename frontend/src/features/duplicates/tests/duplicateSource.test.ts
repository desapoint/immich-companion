import { describe, expect, it } from 'vitest';

import { duplicateSourceLabels, matchesDuplicateSource } from '../utils/duplicateSource';

describe('duplicate discovery source', () => {
  it('keeps shared groups visible under both individual source filters', () => {
    const sources = ['immich_duplicate', 'companion_similarity'] as const;

    expect(matchesDuplicateSource(sources, 'both')).toBe(true);
    expect(matchesDuplicateSource(sources, 'immich')).toBe(true);
    expect(matchesDuplicateSource(sources, 'similarity')).toBe(true);
    expect(duplicateSourceLabels(sources)).toEqual(['Immich', 'Similarity']);
  });

  it('excludes groups from the other source', () => {
    expect(matchesDuplicateSource(['immich_duplicate'], 'similarity')).toBe(false);
    expect(matchesDuplicateSource(['companion_similarity'], 'immich')).toBe(false);
  });
});
