import { render } from 'svelte/server';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
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
    expect(body).toContain('src="/selected/fullsize"');
    expect(body).toContain('src="/reference/fullsize"');
    expect(body).toContain('v2-flicker-reference');
    expect(body).toContain('v2-flicker-selected');
    expect(body).not.toContain('reference-visible');
  });

  it('uses visibility isolation for flicker layers so transparent pixels reveal the backdrop', () => {
    const stylesheet = readFileSync(fileURLToPath(new URL('../../../styles/duplicates.css', import.meta.url)), 'utf8');
    expect(stylesheet).toContain('.v2-flicker-selected.inactive');
    expect(stylesheet).toContain('.v2-flicker-reference{visibility:hidden}');
    expect(stylesheet).toContain('.v2-flicker-reference.reference-visible{visibility:visible}');
  });

  it('clips both swipe layers to complementary sides so transparency cannot reveal the hidden image', async () => {
    const { default: CompareSwipe } = await import('../components/CompareSwipe.svelte');
    const { body } = render(CompareSwipe, {
      props: {
        selectedSrc: '/selected/fullsize',
        referenceSrc: '/reference/fullsize',
        selectedLabel: 'Selected',
        referenceLabel: 'Reference',
        transform: 'translate(0px, 0px) scale(1)',
        split: 40,
      },
    });

    expect(body).toContain('class="v2-compare-layer selected-side"');
    expect(body).toContain('clip-path:inset(0 0 0 40%)');
    expect(body).toContain('clip-path:inset(0 60% 0 0)');
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
