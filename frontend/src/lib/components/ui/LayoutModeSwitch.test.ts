import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import LayoutModeSwitch from './LayoutModeSwitch.svelte';

describe('LayoutModeSwitch', () => {
  it('offers the shared normal and condensed layout options', () => {
    const { body } = render(LayoutModeSwitch, {
      props: {
        mode: 'condensed',
        onchange: () => undefined,
      },
    });

    expect(body).toContain('aria-label="Asset card layout"');
    expect(body).toContain('Card layout');
    expect(body).toContain('Normal');
    expect(body).toContain('Condensed');
    expect(body).toContain('aria-pressed="true"');
  });
});
