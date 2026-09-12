import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import V2AssetTile from './V2AssetTile.svelte';

describe('V2AssetTile', () => {
  it('shows a layout-stable primary control only for selected assets', () => {
    const selected = render(V2AssetTile, { props: { index: 0, assetId: 'asset-1', label: 'photo.jpg', selected: true, selectionMode: true, stackPrimary: true } }).body;
    const unselected = render(V2AssetTile, { props: { index: 0, assetId: 'asset-1', label: 'photo.jpg', selected: false, selectionMode: true } }).body;

    expect(selected).toContain('Selected as stack primary');
    expect(selected).toContain('v2-asset-stack-primary-zone');
    expect(unselected).not.toContain('v2-asset-stack-primary-zone');
  });
});
