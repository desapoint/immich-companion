import type { MediaResource } from './contracts';

export type ThumbnailSource = string | MediaResource;

type CachedThumbnail = {
  source: ThumbnailSource;
  expiresAtMs: number | null;
};

const cache = new Map<string, CachedThumbnail>();
const EXPIRY_SAFETY_MS = 30_000;

function expiryMs(source: ThumbnailSource): number | null {
  if (typeof source === 'string' || !source.expiresAt) return null;
  const value = Date.parse(source.expiresAt);
  return Number.isFinite(value) ? value : null;
}

function usable(entry: CachedThumbnail): boolean {
  return entry.expiresAtMs === null || entry.expiresAtMs - EXPIRY_SAFETY_MS > Date.now();
}

export function cachedThumbnail(cacheKey: string, resolve: () => ThumbnailSource): ThumbnailSource {
  const current = cache.get(cacheKey);
  if (current && usable(current)) return current.source;
  const source = resolve();
  cache.set(cacheKey, { source, expiresAtMs: expiryMs(source) });
  return source;
}

export function clearThumbnailCache(): void {
  cache.clear();
}
