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
    const scrollIntoView = vi.fn();
    const focus = vi.fn();
    const button = { focus };
    const tile = {
      dataset: { assetId: 'asset-2' },
      scrollIntoView,
      querySelector: vi.fn(() => button),
    };
    const container = {
      querySelectorAll: vi.fn(() => [tile]),
    } as unknown as HTMLElement;

    expect(scrollViewedAssetIntoView(container, 'asset-2')).toBe(true);
    expect(scrollIntoView).toHaveBeenCalledWith({ block: 'center', inline: 'nearest' });
    expect(focus).toHaveBeenCalledWith({ preventScroll: true });
    expect(scrollViewedAssetIntoView(container, 'missing')).toBe(false);
  });
});
