import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const pageSource = readFileSync(
  new URL('../components/SimilarityDebugPage.svelte', import.meta.url),
  'utf8',
);

describe('SimilarityDebugPage layout', () => {
  it('keeps debug asset actions inside responsive cards', () => {
    expect(pageSource).toContain('repeat(auto-fill,minmax(min(220px,100%),1fr))');
    expect(pageSource).toContain('similarity-debug-tile-actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))');
    expect(pageSource).toContain('similarity-debug-action-anchor');
    expect(pageSource).toContain('similarity-debug-action-compare');
    expect(pageSource).toContain('similarity-debug-action-remove');
    expect(pageSource).toContain('class:wide={!response || !inGroup || isAnchor}');
    expect(pageSource).toContain('similarity-debug-tile-actions :global(.v2-button){width:100%;min-width:0;max-width:100%');
  });

  it('allows the debug toolbar and long anchor label to wrap without widening the page', () => {
    expect(pageSource).toContain('flex-wrap:wrap');
    expect(pageSource).toContain('max-width:min(100%,360px)');
    expect(pageSource).toContain('text-overflow:ellipsis');
  });

  it('collapses the asset grid to one column on narrow screens', () => {
    expect(pageSource).toContain('@media(max-width:560px)');
    expect(pageSource).toContain('.similarity-debug-assets{grid-template-columns:1fr}');
  });
});
