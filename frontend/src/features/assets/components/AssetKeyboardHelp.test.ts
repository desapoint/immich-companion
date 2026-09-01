import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import AssetKeyboardHelp from './AssetKeyboardHelp.svelte';

describe('AssetKeyboardHelp', () => {
  it('shows group actions only in duplicate review mode', () => {
    const standard = render(AssetKeyboardHelp).body;
    const duplicate = render(AssetKeyboardHelp, { props: { duplicateMode: true } }).body;

    expect(standard).not.toContain('Keep viewed copy');
    expect(duplicate).toContain('Keep viewed copy');
    expect(duplicate).toContain('Delete viewed copy');
    expect(duplicate).toContain('Stack viewed copy');
    expect(duplicate).toContain('Make viewed Stack copy the main image');
  });
});
