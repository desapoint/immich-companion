import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import AssetLayoutControls from './AssetLayoutControls.svelte';

describe('AssetLayoutControls', () => {
  it('offers a discoverable normal and condensed card layout switch', () => {
    const { body } = render(AssetLayoutControls, {
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
