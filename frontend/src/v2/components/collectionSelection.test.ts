import { describe, expect, it } from 'vitest';

import { toggleVisibleSelection, visibleSelectionState } from './collectionSelection';

describe('collectionSelection', () => {
  it('reports none, some, and all for the visible rows only', () => {
    expect(visibleSelectionState(['elsewhere'], ['one', 'two'])).toBe('none');
    expect(visibleSelectionState(['elsewhere', 'one'], ['one', 'two'])).toBe('some');
    expect(visibleSelectionState(['elsewhere', 'one', 'two'], ['one', 'two'])).toBe('all');
    expect(visibleSelectionState([], [])).toBe('none');
  });

  it('selects missing visible rows while retaining selections from other pages', () => {
    expect(toggleVisibleSelection(['elsewhere', 'one'], ['one', 'two'])).toEqual([
      'elsewhere',
      'one',
      'two',
    ]);
  });

  it('unselects all visible rows while retaining selections from other pages', () => {
    expect(toggleVisibleSelection(['elsewhere', 'one', 'two'], ['one', 'two'])).toEqual([
      'elsewhere',
    ]);
  });
});
