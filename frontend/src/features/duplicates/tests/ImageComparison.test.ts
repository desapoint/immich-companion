import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';
import type { MediaResource } from '../../../lib/types/libraryContracts';
import ImageComparison from '../components/ImageComparison.svelte';

function resource(url: string, fallbackUrls: string[]): MediaResource {
  return {
    url,
    fallbackUrls,
    mimeType: 'image/jpeg',
    posterUrl: null,
    delivery: 'decoded',
    originalMimeType: 'image/heic',
    expiresAt: null,
  };
}

describe('ImageComparison', () => {
  it('starts both comparison panes with the compatible media resource primary URL', () => {
    const { body } = render(ImageComparison, {
      props: {
        selectedResource: resource('/selected/fullsize', ['/selected/preview']),
        referenceResource: resource('/reference/fullsize', ['/reference/preview']),
      },
    });
    expect(body).toContain('src="/selected/fullsize"');
    expect(body).toContain('src="/reference/fullsize"');
  });

  it('renders Flicker with both layers loaded and the reference hidden until held', () => {
    const { body } = render(ImageComparison, {
      props: {
        selectedResource: resource('/selected/fullsize', ['/selected/preview']),
        referenceResource: resource('/reference/fullsize', ['/reference/preview']),
        mode: 'Flicker',
      },
    });

    expect(body).toContain('Flicker');
    expect(body).toContain('mode-flicker');
    expect(body).toContain('Hold to show reference');
    expect(body).toContain('aria-pressed="false"');
    expect(body).toContain('style="visibility:visible" aria-hidden="false"');
    expect(body).toContain('style="visibility:hidden" aria-hidden="true"');
    expect(body).toContain('src="/selected/fullsize"');
    expect(body).toContain('src="/reference/fullsize"');
  });

  it('clips both swipe layers to complementary sides so transparency cannot reveal the hidden image', async () => {
    const { default: CompareSwipe } = await import('../components/CompareSwipe.svelte');
    const { body } = render(CompareSwipe, {
      props: {
        pair: {
          selected: { src: '/selected/fullsize', label: 'Selected' },
          reference: { src: '/reference/fullsize', label: 'Reference' },
        },
        transform: 'translate(0px, 0px) scale(1)',
        split: 40,
      },
    });

    expect(body).toContain('style="clip-path:inset(0 0 0 40%);visibility:visible" aria-hidden="false"');
    expect(body).toContain('style="clip-path:inset(0 60% 0 0);visibility:visible" aria-hidden="false"');
  });

  it('uses shared hover controls for Local Changes presentation settings', () => {
    const { body } = render(ImageComparison, {
      props: {
        selectedResource: resource('/selected/fullsize', ['/selected/preview']),
        referenceResource: resource('/reference/fullsize', ['/reference/preview']),
        mode: 'Local changes',
      },
    });

    expect(body).toContain('v2-compare-floating-controls v2-compare-hover v2-local-change-controls');
    expect(body).toContain('v2-range-slider');
    expect(body).toContain('Color');
    expect(body).toContain('Local changes highlight color');
    expect(body).toContain('Grid detail');
    expect(body).toContain('Local changes grid detail');
    expect(body).toContain('32×32');
    expect(body).toContain('Minimum difference visible');
    expect(body).toContain('Minimum visible local difference');
    expect(body).toContain('Minimum highlight intensity');
    expect(body).toContain('#00DCFF');
  });
});
