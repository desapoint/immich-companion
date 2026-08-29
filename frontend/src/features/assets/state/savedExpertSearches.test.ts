import { describe, expect, it } from 'vitest';

import { createSearchCondition, createSearchGroup, serializeSearchGroup } from './assetViewModel';
import {
  decodeSavedExpertSearches,
  removeSavedExpertSearch,
  upsertSavedExpertSearch,
} from './savedExpertSearches';

describe('saved Expert searches', () => {
  it('round-trips a named recursive expression', () => {
    const expression = createSearchGroup('or');
    const condition = createSearchCondition('favorite');
    condition.value = 'true';
    expression.children.push(condition);

    const saved = upsertSavedExpertSearch([], ' Favorites ', expression, new Date('2026-08-28T20:00:00Z'));
    const decoded = decodeSavedExpertSearches(JSON.stringify(saved));

    expect(decoded).toHaveLength(1);
    expect(decoded[0]).toMatchObject({ name: 'Favorites', updated_at: '2026-08-28T20:00:00.000Z' });
    expect(serializeSearchGroup(decoded[0].expression)).toEqual(serializeSearchGroup(expression));
  });

  it('updates a saved search with the same name instead of duplicating it', () => {
    const original = upsertSavedExpertSearch([], 'Review later', createSearchGroup());
    const replacement = createSearchGroup();
    replacement.children.push(createSearchCondition('archived'));

    const updated = upsertSavedExpertSearch(original, 'Review later', replacement);

    expect(updated).toHaveLength(1);
    expect(updated[0].id).toBe(original[0].id);
    expect(updated[0].expression.children).toHaveLength(1);
  });

  it('ignores malformed storage entries and deletes only the selected search', () => {
    const first = upsertSavedExpertSearch([], 'First', createSearchGroup());
    const second = upsertSavedExpertSearch(first, 'Second', createSearchGroup());
    const malformed = JSON.stringify([...second, { id: 'bad', name: 'Bad', expression: {} }]);

    const decoded = decodeSavedExpertSearches(malformed);
    const remaining = removeSavedExpertSearch(decoded, second[0].id);

    expect(decoded).toHaveLength(2);
    expect(remaining.map((search) => search.name)).toEqual(['First']);
    expect(decodeSavedExpertSearches('{broken')).toEqual([]);
  });

  it('requires a non-empty name', () => {
    expect(() => upsertSavedExpertSearch([], '   ', createSearchGroup())).toThrow(
      'Enter a name before saving this search.',
    );
  });
});
