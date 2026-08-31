import { render } from 'svelte/server';
import { describe, expect, it } from 'vitest';

import AssetViewerComparisonTray from './AssetViewerComparisonTray.svelte';

const items = [
  { id: 'selected', label: 'Selected', thumbnailUrl: '/selected.jpg' },
  { id: 'viewed', label: 'Viewed', thumbnailUrl: '/viewed.jpg' },
];

function renderTray(visibleId: string, source: 'stack' | 'duplicate' = 'stack'): string {
  return render(AssetViewerComparisonTray, {
    props: {
      items,
      source,
      activation: 'click',
      selectedId: 'selected',
      visibleId,
      onpreview: () => undefined,
      onrestore: () => undefined,
      oncommit: () => undefined,
      onselectviewed: () => undefined,
    },
  }).body;
}

describe('AssetViewerComparisonTray', () => {
  it('reserves the select-viewed control before the image count', () => {
    const selected = renderTray('selected');
    const viewed = renderTray('viewed');

    expect(selected).toContain('select-viewed');
    expect(selected).toMatch(/class="select-viewed[^"]* hidden/);
    expect(selected).toContain('disabled');
    expect(viewed).not.toMatch(/class="select-viewed[^"]* hidden/);
    expect(viewed.indexOf('Use viewed as selected')).toBeLessThan(viewed.indexOf('2 images'));
  });

  it('identifies duplicate group members without calling them similar images', () => {
    const body = renderTray('selected', 'duplicate');

    expect(body).toContain('Duplicate copies');
    expect(body).not.toContain('Similar images');
    expect(body).toContain('aria-label="duplicate image comparison"');
    expect(body).toContain('aria-label="Duplicate copies"');
  });
});
