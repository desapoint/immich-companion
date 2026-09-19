import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';
import type { MediaResource } from '../data/contracts';
import V2ImageComparison from './V2ImageComparison.svelte';

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

describe('V2ImageComparison', () => {
  it('starts both comparison panes with the compatible media resource primary URL', () => {
    const { body } = render(V2ImageComparison, {
      props: {
        selectedResource: resource('/selected/fullsize', ['/selected/preview']),
        referenceResource: resource('/reference/fullsize', ['/reference/preview']),
      },
    });
    expect(body).toContain('src="/selected/fullsize"');
    expect(body).toContain('src="/reference/fullsize"');
  });

  it('renders Flicker with both layers loaded and the reference hidden until held', () => {
    const { body } = render(V2ImageComparison, {
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
    expect(body).not.toContain('reference-visible');
  });

  it('uses shared hover controls for Local Changes presentation settings', () => {
    const { body } = render(V2ImageComparison, {
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
