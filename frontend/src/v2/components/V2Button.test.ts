import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2Button from './V2Button.svelte';

describe('V2Button', () => {
  it('exposes optional toggle and keyboard-shortcut semantics', () => {
    const { body } = render(V2Button, {
      props: {
        active: true,
        ariaLabel: 'Deselect shown asset',
        ariaPressed: true,
        ariaKeyshortcuts: 'Space',
        children: (() => 'Selected') as never,
      },
    });

    expect(body).toContain('aria-label="Deselect shown asset"');
    expect(body).toContain('aria-pressed="true"');
    expect(body).toContain('aria-keyshortcuts="Space"');
  });
});
