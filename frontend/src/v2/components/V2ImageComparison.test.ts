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
});
