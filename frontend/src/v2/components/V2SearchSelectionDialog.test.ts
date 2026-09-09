import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2SearchSelectionDialog from './V2SearchSelectionDialog.svelte';

describe('V2SearchSelectionDialog', () => {
  it('offers keep, clear, and cancel choices with exact all-matching semantics', () => {
    const { body } = render(V2SearchSelectionDialog, {
      props: { selectedCount: 25_000, allMatching: true, onkeep: () => undefined, onclear: () => undefined, onclose: () => undefined },
    });

    expect(body).toContain('25,000 assets are selected');
    expect(body).toContain('preserve the exact assets matched by the current search');
    expect(body).toContain('Clear selection &amp; search');
    expect(body).toContain('Keep selection &amp; search');
    expect(body).toContain('Cancel');
  });
});
