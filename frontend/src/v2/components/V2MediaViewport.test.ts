import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import type { MediaResource } from '../data/contracts';
import V2MediaViewport, { nextMediaSourceIndex } from './V2MediaViewport.svelte';

const imageResource: MediaResource = {
  url: '/original',
  fallbackUrls: ['/fullsize', '/preview'],
  mimeType: 'image/png',
  posterUrl: null,
  delivery: 'original',
  originalMimeType: 'image/png',
  expiresAt: null,
};

describe('V2MediaViewport', () => {
  it('advances through ordered image fallbacks before reporting exhaustion', () => {
    expect(nextMediaSourceIndex(0, 3)).toBe(1);
    expect(nextMediaSourceIndex(1, 3)).toBe(2);
    expect(nextMediaSourceIndex(2, 3)).toBeNull();
    expect(render(V2MediaViewport, {
      props: { resource: imageResource, assetType: 'IMAGE', alt: 'Fixture' },
    }).body).toContain('src="/original"');
  });

  it('renders the compatible playback resource with its poster', () => {
    const resource: MediaResource = {
      ...imageResource,
      url: '/api/assets/video/video/playback',
      fallbackUrls: [],
      mimeType: 'video/mp4',
      posterUrl: '/poster',
      delivery: 'transcoded',
      originalMimeType: 'video/quicktime',
    };
    const { body } = render(V2MediaViewport, {
      props: { resource, assetType: 'VIDEO', alt: 'Movie' },
    });
    expect(body).toContain(`src="${resource.url}"`);
    expect(body).toContain('poster="/poster"');
    expect(body).toContain('aria-label="Seek video"');
    expect(body).toContain('aria-label="Video volume"');
  });
});
