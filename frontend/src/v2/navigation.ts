export const V2_PAGE_KEYS = [
  'status',
  'assets',
  'restore',
  'duplicates',
  'albums',
  'tags',
  'settings',
  'docs',
  'playground',
] as const;

export type V2PageKey = (typeof V2_PAGE_KEYS)[number];
export type V2AssetFilterHandoff = { albumIds?: string[]; tagIds?: string[] };

export const V2_DEFAULT_PAGE: V2PageKey = 'status';
export const V2_ASSET_FILTER_HANDOFF_KEY = 'immichCompanionV2AssetFilterHandoff';

const v2PageKeySet = new Set<string>(V2_PAGE_KEYS);

export function isV2PageKey(value: string): value is V2PageKey {
  return v2PageKeySet.has(value);
}

export function v2PagePath(key: V2PageKey): string {
  return key === 'status' ? '/' : `/${key}`;
}

export function v2AssetViewerPath(assetId: string): string {
  return `${v2PagePath('assets')}/${encodeURIComponent(assetId)}`;
}

export function v2AssetIdFromPath(pathname: string): string | null {
  const normalizedPath = pathname.replace(/\/+$/, '') || '/';
  const match = /^\/assets\/([^/]+)$/.exec(normalizedPath);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return null;
  }
}

export function v2PageFromPath(pathname: string): V2PageKey {
  const normalizedPath = pathname.replace(/\/+$/, '') || '/';
  if (normalizedPath === '/') return V2_DEFAULT_PAGE;
  if (v2AssetIdFromPath(normalizedPath) !== null) return 'assets';

  const match = /^\/([^/]+)$/.exec(normalizedPath);
  return match && isV2PageKey(match[1]) ? match[1] : V2_DEFAULT_PAGE;
}

/**
 * Return the canonical frontend URL for an old V2 URL, or null when no
 * redirect is needed. This intentionally only handles frontend paths; API
 * endpoints under /api/v2 remain versioned and are not redirected.
 */
export function legacyV2RedirectPath(pathname: string): string | null {
  const normalizedPath = pathname.replace(/\/+$/, '') || '/';
  if (normalizedPath !== '/v2' && !normalizedPath.startsWith('/v2/')) return null;

  if (normalizedPath === '/v2') return '/';

  const legacyPath = normalizedPath.slice('/v2/'.length);
  const assetMatch = /^assets\/([^/]+)$/.exec(legacyPath);
  if (assetMatch) return `/assets/${assetMatch[1]}`;
  if (isV2PageKey(legacyPath)) return v2PagePath(legacyPath);
  return '/';
}

export function v2PageFromLegacyHash(hash: string): V2PageKey | null {
  const value = hash.startsWith('#') ? hash.slice(1) : hash;
  return isV2PageKey(value) ? value : null;
}

export function storeV2AssetFilterHandoff(handoff: V2AssetFilterHandoff, storage: Pick<Storage, 'setItem'> = sessionStorage): void {
  storage.setItem(V2_ASSET_FILTER_HANDOFF_KEY, JSON.stringify(handoff));
}

export function consumeV2AssetFilterHandoff(storage: Pick<Storage, 'getItem' | 'removeItem'> = sessionStorage): V2AssetFilterHandoff | null {
  const raw = storage.getItem(V2_ASSET_FILTER_HANDOFF_KEY);
  if (!raw) return null;
  storage.removeItem(V2_ASSET_FILTER_HANDOFF_KEY);
  try {
    return JSON.parse(raw) as V2AssetFilterHandoff;
  } catch {
    return null;
  }
}
