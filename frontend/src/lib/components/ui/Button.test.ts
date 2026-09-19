import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import Button from './Button.svelte';

describe('Button', () => {
  it('exposes optional toggle and keyboard-shortcut semantics', () => {
    const { body } = render(Button, {
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
