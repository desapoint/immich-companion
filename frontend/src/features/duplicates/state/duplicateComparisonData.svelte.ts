import type { AssetRecord, DuplicateSimilarityEvidence, MediaResource } from '../types/contracts';
import { libraryData } from '../../../app/data/currentDataSource.svelte';
import { loadLocalChangeDiagnostics, type LocalChangeDiagnostics } from '../utils/localChangeDiagnostics';
import { loadImmichLibraries } from '../../../lib/api/duplicatePolicyApi';
import { comparisonAlignmentSettingsRepository } from '../api/comparisonAlignmentSettingsRepository';

function assetSetKey(ids: readonly string[]): string { return [...ids].sort().join('\u0000'); }
function diagnosticsPairKey(selectedId: string, referenceId: string, displacement: number, rotation: number, zoom: number): string {
  return `${selectedId}\u0000${referenceId}\u0000${displacement}\u0000${rotation}\u0000${zoom}`;
}
function identicalDiagnostics(assetId: string): LocalChangeDiagnostics {
  const side = 32;
  return { available: true, selectedAssetId: assetId, referenceAssetId: assetId, changedPercent: 0, localizedChangedPercent: 0, coherentChangedPercent: 0, largestChangedRegionPercent: 0, substantialRegionCount: 0, alignedChangedPercent: 0, rawSimilarityPercent: 100, alignedSimilarityPercent: 100, alignmentApplied: false, alignmentShiftPercent: 0, alignmentRotationDegrees: 0, alignmentOverlapPercent: 100, rows: side, columns: side, cells: Array.from({ length: side }, () => Array<number>(side).fill(0)), source: null };
}

export class DuplicateComparisonDataController {
  assets = $state<AssetRecord[]>([]);
  libraryNames = $state<Map<string, string>>(new Map());
  loading = $state(false);
  loadError = $state('');
  localDiagnostics = $state<LocalChangeDiagnostics | null>(null);
  localDiagnosticsLoading = $state(false);
  localDiagnosticsError = $state('');
  private loadGeneration = 0;
  private loadedAssetSetKey = '';
  private loadingAssetSetKey = '';
  private libraryNamesPromise: Promise<Map<string, string>> | null = null;
  private diagnosticsGeneration = 0;
  private readonly diagnosticsCache = new Map<string, LocalChangeDiagnostics>();

  resource(asset: AssetRecord | undefined): MediaResource {
    if (!asset) return { url: '', fallbackUrls: [], mimeType: null, posterUrl: null, delivery: 'preview', originalMimeType: null, expiresAt: null };
    if (asset.asset_type === 'VIDEO') {
      const url = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640"><rect width="960" height="640" fill="#222831"/><circle cx="480" cy="320" r="82" fill="#ffffff22"/><path d="M455 270 545 320 455 370Z" fill="white"/><text x="480" y="450" text-anchor="middle" fill="white" font-family="sans-serif" font-size="34">Video asset</text></svg>');
      return { url, fallbackUrls: [], mimeType: 'image/svg+xml', posterUrl: null, delivery: 'preview', originalMimeType: null, expiresAt: null };
    }
    // Use the shared viewer media contract so browser-supported formats keep
    // their original representation (including alpha) and fall back through
    // Immich fullsize/preview derivatives only when the original cannot load.
    // Unsupported formats still resolve to the bounded derivative chain.
    return libraryData.media.view(asset);
  }

  async load(ids: readonly string[], open: boolean): Promise<void> {
    if (!open) return;
    const requestedKey = assetSetKey(ids);
    if (requestedKey === this.loadedAssetSetKey) {
      this.loading = false;
      return;
    }
    if (requestedKey === this.loadingAssetSetKey) return;
    const generation = ++this.loadGeneration;
    this.loadingAssetSetKey = requestedKey;
    this.loading = ids.length > 0 && this.loadedAssetSetKey !== requestedKey;
    this.loadError = '';
    try {
      const [nextAssets, nextLibraryNames] = await Promise.all([this.getDetailedAssets([...ids]), this.getLibraryNames()]);
      if (generation !== this.loadGeneration) return;
      this.assets = nextAssets;
      this.libraryNames = nextLibraryNames;
      this.loadedAssetSetKey = assetSetKey(nextAssets.map((asset) => asset.id));
    } catch (error) {
      if (generation === this.loadGeneration) this.loadError = error instanceof Error ? error.message : 'Could not load comparison assets.';
    } finally {
      if (generation === this.loadGeneration) {
        this.loading = false;
        this.loadingAssetSetKey = '';
      }
    }
  }

  async loadDiagnostics(selected: AssetRecord | undefined, reference: AssetRecord | undefined, open: boolean): Promise<void> {
    const selectedId = selected?.id ?? '', referenceId = reference?.id ?? '', generation = ++this.diagnosticsGeneration;
    const controller = new AbortController();
    this.localDiagnostics = null;
    this.localDiagnosticsError = '';
    this.localDiagnosticsLoading = false;
    if (!open || !selectedId || !referenceId || selected?.asset_type !== 'IMAGE' || reference?.asset_type !== 'IMAGE') return;
    if (selectedId === referenceId) { this.localDiagnostics = identicalDiagnostics(selectedId); return; }
    this.localDiagnosticsLoading = true;
    try {
      // Verify the server's current comparison limits before trusting a cached
      // pair. This lets another browser's saved settings invalidate local results.
      const settings = await comparisonAlignmentSettingsRepository.load(controller.signal);
      if (generation !== this.diagnosticsGeneration) return;
      const key = diagnosticsPairKey(
        selectedId,
        referenceId,
        settings.maxDisplacementPercent,
        settings.maxRotationDegrees,
        settings.maxZoomPercent,
      );
      const cached = this.diagnosticsCache.get(key);
      if (cached) {
        this.localDiagnostics = cached;
        return;
      }
      const result = await loadLocalChangeDiagnostics(
        selectedId,
        referenceId,
        controller.signal,
        settings,
      );
      if (generation !== this.diagnosticsGeneration) return;
      const resultKey = diagnosticsPairKey(
        selectedId,
        referenceId,
        result.comparisonMaxDisplacementPercent ?? settings.maxDisplacementPercent,
        result.comparisonMaxRotationDegrees ?? settings.maxRotationDegrees,
        result.comparisonMaxZoomPercent ?? settings.maxZoomPercent,
      );
      this.diagnosticsCache.set(resultKey, result);
      this.localDiagnostics = result;
    } catch (error) {
      if (generation !== this.diagnosticsGeneration || controller.signal.aborted) return;
      this.localDiagnosticsError = error instanceof Error ? error.message : 'Could not load localized change diagnostics.';
    } finally {
      if (generation === this.diagnosticsGeneration) this.localDiagnosticsLoading = false;
    }
  }

  invalidateAssets(): void { this.loadGeneration += 1; this.loadingAssetSetKey = ''; }
  invalidateDiagnostics(): void { this.diagnosticsGeneration += 1; }
  invalidate(): void { this.invalidateAssets(); this.invalidateDiagnostics(); }

  private getLibraryNames(): Promise<Map<string, string>> {
    this.libraryNamesPromise ??= loadImmichLibraries().then((libraries) => new Map(libraries.map((library) => [library.id, library.name]))).catch(() => new Map());
    return this.libraryNamesPromise;
  }

  private async getDetailedAssets(ids: string[]): Promise<AssetRecord[]> {
    const items: AssetRecord[] = [];
    for (let index = 0; index < ids.length; index += 8) {
      const batch = await Promise.all(ids.slice(index, index + 8).map((id) => libraryData.assets.details(id)));
      for (const item of batch) if (item) items.push(item);
    }
    return items;
  }
}
