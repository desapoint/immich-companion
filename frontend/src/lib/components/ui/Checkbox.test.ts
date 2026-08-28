import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import Checkbox from './Checkbox.svelte';

describe('Checkbox', () => {
  it('renders a themed accessible checked control', () => {
    const { body } = render(Checkbox, {
      props: {
        checked: true,
        label: 'Select asset',
        hiddenLabel: true,
      },
    });

    expect(body).toContain('type="checkbox"');
    expect(body).toContain('aria-label="Select asset"');
    expect(body).toContain('checked');
    expect(body).toContain('class="control');
  });
});
