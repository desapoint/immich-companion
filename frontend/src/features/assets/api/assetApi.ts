import type {
  AssetDetail,
  AlbumOption,
  AssetSearchResponse,
  AssetSort,
  AssetSyncResult,
  SearchGroup,
  AssetViewerMedia,
  TagOption,
} from '../types/assets';
import type { MediaPreviewItem } from '../../../lib/types/media';
import { createDefaultAssetSort } from '../state/assetSort';
import { serializeSearchGroup } from '../state/assetViewModel';
import { DEFAULT_ASSET_PAGE_SIZE } from '../state/assetPagination';

async function requestJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    headers: { Accept: 'application/json', ...init?.headers },
    ...init,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body && typeof body.detail === 'string' ? body.detail : null;
    throw new Error(detail ?? `Companion request failed with HTTP ${response.status}.`);
  }
  return (await response.json()) as T;
}

export function normalizeAssetSearchResponse(response: AssetSearchResponse): AssetSearchResponse {
  return {
    ...response,
    items: response.items.map((asset) => ({
      ...asset,
      albums: asset.albums ?? [],
      tags: asset.tags ?? [],
      stack: asset.stack
        ? { ...asset.stack, assets: asset.stack.assets ?? [] }
        : null,
      source: asset.source ?? { kind: 'upload', library_id: null, original_path: null },
      immich_url: asset.immich_url ?? null,
    })),
  };
}

export function buildAssetSearchRequest(
  expression: SearchGroup,
  page: number,
  pageSize = DEFAULT_ASSET_PAGE_SIZE,
  sort: AssetSort = createDefaultAssetSort(),
): Record<string, unknown> {
  return {
    expression: serializeSearchGroup(expression),
    sort_field: sort.field,
    sort_direction: sort.direction,
    page,
    page_size: pageSize,
  };
}

export async function searchAssets(
  expression: SearchGroup,
  page: number,
  pageSize = DEFAULT_ASSET_PAGE_SIZE,
  sort: AssetSort = createDefaultAssetSort(),
  signal?: AbortSignal,
): Promise<AssetSearchResponse> {
  const response = await requestJson<AssetSearchResponse>('/api/assets/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buildAssetSearchRequest(expression, page, pageSize, sort)),
    signal,
  });
  return normalizeAssetSearchResponse(response);
}

export function getAlbumOptions(signal?: AbortSignal): Promise<AlbumOption[]> {
  return requestJson('/api/albums', { signal });
}

export function getTagOptions(signal?: AbortSignal): Promise<TagOption[]> {
  return requestJson('/api/tags', { signal });
}

export function synchronizeAssets(): Promise<AssetSyncResult> {
  return requestJson('/api/assets/sync', { method: 'POST' });
}

export function getAssetDetail(assetId: string, signal?: AbortSignal): Promise<AssetDetail> {
  return requestJson(`/api/assets/${encodeURIComponent(assetId)}`, { signal });
}

export function assetMediaUrl(assetId: string, size: 'thumbnail' | 'preview'): string {
  return `/api/assets/${encodeURIComponent(assetId)}/thumbnail?size=${size}`;
}

export function assetOriginalUrl(assetId: string): string {
  return `/api/assets/${encodeURIComponent(assetId)}/original`;
}

export function buildAssetPreviewItems(assets: AssetViewerMedia[]): MediaPreviewItem[] {
  return assets.map((asset) => ({
    id: asset.id,
    label: asset.original_file_name,
    thumbnailUrl: assetMediaUrl(asset.id, 'thumbnail'),
    meta: asset.width && asset.height ? `${asset.width} × ${asset.height}` : asset.type,
  }));
}
