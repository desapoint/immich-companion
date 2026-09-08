import { describe, expect, it, vi } from 'vitest';
import { scrollViewedAssetIntoView, viewerPageForPosition } from './viewerCollectionNavigation';

describe('viewer collection navigation', () => {
  it('maps absolute viewer positions to collection pages', () => {
    expect(viewerPageForPosition(1, 24)).toBe(1);
    expect(viewerPageForPosition(24, 24)).toBe(1);
    expect(viewerPageForPosition(25, 24)).toBe(2);
    expect(viewerPageForPosition(49, 24)).toBe(3);
    expect(viewerPageForPosition(null, 24)).toBeNull();
  });

  it('scrolls and focuses the matching asset tile', () => {
    const container = document.createElement('div');
    const tile = document.createElement('div');
    tile.dataset.assetId = 'asset-2';
    const button = document.createElement('button');
    button.className = 'v2-asset-main';
    tile.append(button);
    container.append(tile);
    tile.scrollIntoView = vi.fn();
    button.focus = vi.fn();

    expect(scrollViewedAssetIntoView(container, 'asset-2')).toBe(true);
    expect(tile.scrollIntoView).toHaveBeenCalledWith({ block: 'center', inline: 'nearest' });
    expect(button.focus).toHaveBeenCalledWith({ preventScroll: true });
    expect(scrollViewedAssetIntoView(container, 'missing')).toBe(false);
  });
});
