import type {
  AssetDetail,
  AlbumOption,
  AssetSearchResponse,
  AssetSyncResult,
  SearchGroup,
} from '../types/assets';
import { serializeSearchGroup } from '../state/assetViewModel';

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

export function buildAssetSearchRequest(
  expression: SearchGroup,
  page: number,
  pageSize = 48,
): Record<string, unknown> {
  return { expression: serializeSearchGroup(expression), page, page_size: pageSize };
}

export function searchAssets(
  expression: SearchGroup,
  page: number,
  signal?: AbortSignal,
): Promise<AssetSearchResponse> {
  return requestJson('/api/assets/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buildAssetSearchRequest(expression, page)),
    signal,
  });
}

export function getAlbumOptions(signal?: AbortSignal): Promise<AlbumOption[]> {
  return requestJson('/api/albums', { signal });
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
