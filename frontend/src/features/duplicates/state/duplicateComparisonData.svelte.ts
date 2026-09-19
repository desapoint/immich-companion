import type { AssetRecord, DuplicateSimilarityEvidence, MediaResource } from '../types/contracts';
import { libraryData } from '../../../app/data/currentDataSource.svelte';
import { loadLocalChangeDiagnostics, type LocalChangeDiagnostics } from '../utils/localChangeDiagnostics';
import { loadImmichLibraries } from '../../../lib/api/duplicatePolicyApi';

function assetSetKey(ids: readonly string[]): string { return [...ids].sort().join('\u0000'); }
function diagnosticsPairKey(selectedId: string, referenceId: string): string { return `${selectedId}\u0000${referenceId}`; }
function identicalDiagnostics(assetId: string): LocalChangeDiagnostics {
  const side = 32;
  return { available: true, selectedAssetId: assetId, referenceAssetId: assetId, changedPercent: 0, localizedChangedPercent: 0, coherentChangedPercent: 0, largestChangedRegionPercent: 0, substantialRegionCount: 0, rows: side, columns: side, cells: Array.from({ length: side }, () => Array<number>(side).fill(0)), source: null };
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
  private libraryNamesPromise: Promise<Map<string, string>> | null = null;
  private diagnosticsGeneration = 0;
  private readonly diagnosticsCache = new Map<string, LocalChangeDiagnostics>();

  resource(asset: AssetRecord | undefined): MediaResource {
    if (!asset) return { url: '', fallbackUrls: [], mimeType: null, posterUrl: null, delivery: 'preview', originalMimeType: null, expiresAt: null };
    if (asset.asset_type === 'VIDEO') {
      const url = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640"><rect width="960" height="640" fill="#222831"/><circle cx="480" cy="320" r="82" fill="#ffffff22"/><path d="M455 270 545 320 455 370Z" fill="white"/><text x="480" y="450" text-anchor="middle" fill="white" font-family="sans-serif" font-size="34">Video asset</text></svg>');
      return { url, fallbackUrls: [], mimeType: 'image/svg+xml', posterUrl: null, delivery: 'preview', originalMimeType: null, expiresAt: null };
    }
    return libraryData.media.view(asset);
  }

  async load(ids: readonly string[], open: boolean): Promise<void> {
    if (!open) return;
    const generation = ++this.loadGeneration;
    const requestedKey = assetSetKey(ids);
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
      if (generation === this.loadGeneration) this.loading = false;
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
    const key = diagnosticsPairKey(selectedId, referenceId), cached = this.diagnosticsCache.get(key);
    if (cached) { this.localDiagnostics = cached; return; }
    this.localDiagnosticsLoading = true;
    try {
      const result = await loadLocalChangeDiagnostics(selectedId, referenceId, controller.signal);
      if (generation !== this.diagnosticsGeneration) return;
      this.diagnosticsCache.set(key, result);
      this.localDiagnostics = result;
    } catch (error) {
      if (generation !== this.diagnosticsGeneration || controller.signal.aborted) return;
      this.localDiagnosticsError = error instanceof Error ? error.message : 'Could not load localized change diagnostics.';
    } finally {
      if (generation === this.diagnosticsGeneration) this.localDiagnosticsLoading = false;
    }
  }

  invalidate(): void { this.loadGeneration += 1; this.diagnosticsGeneration += 1; }

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
