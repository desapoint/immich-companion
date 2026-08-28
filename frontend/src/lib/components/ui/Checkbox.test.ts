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

  it('keeps the checkmark mounted and supports circular card controls', () => {
    const checked = render(Checkbox, {
      props: { checked: true, label: 'Select asset', hiddenLabel: true, shape: 'circle' },
    }).body;
    const unchecked = render(Checkbox, {
      props: { checked: false, label: 'Select asset', hiddenLabel: true, shape: 'circle' },
    }).body;

    expect(checked).toContain('circle');
    expect(checked).toMatch(/class="checkmark [^"]* visible"/);
    expect(unchecked).toContain('checkmark');
    expect(unchecked).not.toMatch(/class="checkmark [^"]* visible"/);
  });
});
