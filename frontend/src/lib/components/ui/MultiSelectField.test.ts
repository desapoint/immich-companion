import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import MultiSelectField from './MultiSelectField.svelte';

const props = {
  id: 'test-values',
  label: 'Values',
  values: ['first'],
  options: [
    { value: 'first', label: 'First' },
    { value: 'second', label: 'Second' },
  ],
  onchange: () => undefined,
};

describe('MultiSelectField', () => {
  it('is a custom multi-select with option search disabled by default', () => {
    const { body } = render(MultiSelectField, { props });

    expect(body).toContain('aria-haspopup="listbox"');
    expect(body).toContain('data-searchable="false"');
    expect(body).not.toContain('<select');
    expect(body).not.toContain('type="search"');
  });

  it('adds value search only when the caller enables it', () => {
    const { body } = render(MultiSelectField, {
      props: { ...props, searchable: true },
    });

    expect(body).not.toContain('<select');
    expect(body).toContain('aria-haspopup="listbox"');
    expect(body).toContain('data-searchable="true"');
  });
});
