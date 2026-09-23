import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const assetsPage = readFileSync(resolve(process.cwd(), 'src/features/assets/components/AssetsPage.svelte'), 'utf8');
const assetGrid = readFileSync(resolve(process.cwd(), 'src/features/assets/components/AssetGrid.svelte'), 'utf8');

describe('mobile Assets polish', () => {
  it('caps the effective phone grid at three columns without changing the selected value', () => {
    expect(assetGrid).toContain('--v2-mobile-asset-columns:${Math.min(columns, 3)}');
    expect(assetGrid).toContain('@media (max-width: 380px)');
    expect(assetGrid).toContain('repeat(var(--v2-mobile-asset-columns), minmax(0, 1fr))');
    expect(assetsPage).toContain('value={collection.columns}');
  });

  it('labels the browse toolbar selection controls on small phones', () => {
    expect(assetsPage).toContain('class="v2-asset-toolbar-action"');
    expect(assetsPage).toContain('<span class="v2-asset-toolbar-label">Visible</span>');
    expect(assetsPage).toContain('<span class="v2-asset-toolbar-label">All</span>');
    expect(assetsPage).toContain('@media(max-width:380px){.v2-asset-toolbar-label{display:inline}}');
  });
});
