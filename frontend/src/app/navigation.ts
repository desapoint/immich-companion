export const PAGE_KEYS = [
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

export type PageKey = (typeof PAGE_KEYS)[number];
export type AssetFilterHandoff = { albumIds?: string[]; tagIds?: string[] };

export const DEFAULT_PAGE: PageKey = 'status';
export const ASSET_FILTER_HANDOFF_KEY = 'immichCompanionV2AssetFilterHandoff';

const pageKeySet = new Set<string>(PAGE_KEYS);

export function isPageKey(value: string): value is PageKey {
  return pageKeySet.has(value);
}

export function pagePath(key: PageKey): string {
  return key === 'status' ? '/' : `/${key}`;
}

export function assetViewerPath(assetId: string): string {
  return `${pagePath('assets')}/${encodeURIComponent(assetId)}`;
}

export function assetIdFromPath(pathname: string): string | null {
  const normalizedPath = pathname.replace(/\/+$/, '') || '/';
  const match = /^\/assets\/([^/]+)$/.exec(normalizedPath);
  if (!match) return null;
  try {
    return decodeURIComponent(match[1]);
  } catch {
    return null;
  }
}

export function pageFromPath(pathname: string): PageKey {
  const normalizedPath = pathname.replace(/\/+$/, '') || '/';
  if (normalizedPath === '/') return DEFAULT_PAGE;
  if (assetIdFromPath(normalizedPath) !== null) return 'assets';

  const match = /^\/([^/]+)$/.exec(normalizedPath);
  return match && isPageKey(match[1]) ? match[1] : DEFAULT_PAGE;
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
  if (isPageKey(legacyPath)) return pagePath(legacyPath);
  return '/';
}

export function pageFromLegacyHash(hash: string): PageKey | null {
  const value = hash.startsWith('#') ? hash.slice(1) : hash;
  return isPageKey(value) ? value : null;
}

export function storeAssetFilterHandoff(handoff: AssetFilterHandoff, storage: Pick<Storage, 'setItem'> = sessionStorage): void {
  storage.setItem(ASSET_FILTER_HANDOFF_KEY, JSON.stringify(handoff));
}

export function consumeAssetFilterHandoff(storage: Pick<Storage, 'getItem' | 'removeItem'> = sessionStorage): AssetFilterHandoff | null {
  const raw = storage.getItem(ASSET_FILTER_HANDOFF_KEY);
  if (!raw) return null;
  storage.removeItem(ASSET_FILTER_HANDOFF_KEY);
  try {
    return JSON.parse(raw) as AssetFilterHandoff;
  } catch {
    return null;
  }
}
