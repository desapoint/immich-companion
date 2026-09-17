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

  it('renders the Local Changes emphasis control as display-only presentation state', () => {
    const { body } = render(V2ImageComparison, {
      props: {
        selectedResource: resource('/selected/fullsize', ['/selected/preview']),
        referenceResource: resource('/reference/fullsize', ['/reference/preview']),
        mode: 'Local changes',
      },
    });

    expect(body).toContain('Minimum highlight intensity');
    expect(body).toContain('type="range"');
    expect(body).toContain('min="0"');
    expect(body).toContain('max="100"');
    expect(body).toContain('Actual percentages stay unchanged');
    expect(body).toContain('0% cells remain clear');
  });
});
