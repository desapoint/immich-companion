import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2SortableHeader from './V2SortableHeader.svelte';

describe('V2SortableHeader', () => {
  it('exposes the active direction and the next toggle direction', () => {
    const ascending = render(V2SortableHeader, {
      props: { field: 'name', label: 'Name', sort: 'name:asc', onsort: () => undefined },
    }).body;
    const descending = render(V2SortableHeader, {
      props: { field: 'name', label: 'Name', sort: 'name:desc', onsort: () => undefined },
    }).body;

    expect(ascending).toContain('aria-sort="ascending"');
    expect(ascending).toContain('title="Sort Name descending"');
    expect(ascending).toContain('lucide-arrow-down');
    expect(descending).toContain('aria-sort="descending"');
    expect(descending).toContain('title="Sort Name ascending"');
    expect(descending).toContain('lucide-arrow-up');
  });

  it('starts an inactive column in ascending order', () => {
    const { body } = render(V2SortableHeader, {
      props: { field: 'assets', label: 'Assets', sort: 'name:desc', onsort: () => undefined },
    });

    expect(body).toContain('aria-sort="none"');
    expect(body).toContain('title="Sort Assets ascending"');
  });
});
