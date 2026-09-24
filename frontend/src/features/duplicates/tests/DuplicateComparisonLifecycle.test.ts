import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

const viewerSource = readFileSync(new URL('../components/DuplicateCompareViewer.svelte', import.meta.url), 'utf8');
const controllerSource = readFileSync(new URL('../state/duplicateComparisonData.svelte.ts', import.meta.url), 'utf8');

describe('duplicate comparison loading lifecycle', () => {
  it('invalidates asset and diagnostics requests independently', () => {
    expect(viewerSource).toContain('$effect(() => { void comparisonData.load(assetIds, open); });');
    expect(viewerSource).toContain('return () => comparisonData.invalidateDiagnostics()');
    expect(controllerSource).toContain('invalidateAssets(): void');
    expect(controllerSource).toContain('invalidateDiagnostics(): void');
  });

  it('deduplicates equivalent in-flight asset loads', () => {
    expect(controllerSource).toContain('private loadingAssetSetKey = \'\';');
    expect(controllerSource).toContain('if (requestedKey === this.loadingAssetSetKey) return;');
    expect(controllerSource).toContain('this.loadingAssetSetKey = \'\';');
  });

  it('uses the shared original-first media contract for comparison images', () => {
    expect(controllerSource).toContain('return libraryData.media.view(asset);');
    expect(controllerSource).not.toContain("assetThumbnailUrl(asset.id, 'preview')");
    expect(controllerSource).not.toContain("mimeType: 'image/jpeg'");
  });
});
