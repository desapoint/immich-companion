import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import AssetKeyboardHelp from './AssetKeyboardHelp.svelte';

describe('AssetKeyboardHelp', () => {
  it('shows group actions only in duplicate review mode', () => {
    const standard = render(AssetKeyboardHelp).body;
    const duplicate = render(AssetKeyboardHelp, { props: { duplicateMode: true } }).body;

    expect(standard).not.toContain('Resolve duplicate group');
    expect(duplicate).toContain('Use viewed copy as primary');
    expect(duplicate).toContain('Resolve duplicate group');
    expect(duplicate).toContain('Stack all copies');
    expect(duplicate).toContain('Skip / review later');
  });
});
