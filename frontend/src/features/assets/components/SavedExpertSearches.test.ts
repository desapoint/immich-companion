import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import { createSearchGroup } from '../state/assetViewModel';
import SavedExpertSearches from './SavedExpertSearches.svelte';
import SearchConditionRow from './SearchConditionRow.svelte';

describe('saved Expert search controls', () => {
  it('renders named save, load, and delete controls without requiring browser storage during SSR', () => {
    const { body } = render(SavedExpertSearches, {
      props: {
        expression: createSearchGroup(),
        onload: () => undefined,
      },
    });

    expect(body).toContain('Saved searches');
    expect(body).toContain('Search name');
    expect(body).toContain('Save current');
    expect(body).toContain('Load');
    expect(body).toContain('Delete');
  });

  it('places the remove control in a field-aligned wrapper', () => {
    const { body } = render(SearchConditionRow, {
      props: {
        condition: {
          id: 'condition-test',
          kind: 'condition',
          field: 'filename',
          operator: 'contains',
          value: '',
        },
        albums: [],
        tags: [],
        onremove: () => undefined,
      },
    });

    expect(body).toContain('class="remove-field');
    expect(body).toContain('aria-label="Remove condition"');
  });
});
