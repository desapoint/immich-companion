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

export const V2_DEFAULT_PAGE: V2PageKey = 'settings';
export const V2_ASSET_FILTER_HANDOFF_KEY = 'immichCompanionV2AssetFilterHandoff';

const v2PageKeySet = new Set<string>(V2_PAGE_KEYS);

export function isV2PageKey(value: string): value is V2PageKey {
  return v2PageKeySet.has(value);
}

export function v2PagePath(key: V2PageKey): string {
  return `/v2/${key}`;
}

export function v2PageFromPath(pathname: string): V2PageKey {
  const normalizedPath = pathname.replace(/\/+$/, '') || '/';
  if (normalizedPath === '/v2') return V2_DEFAULT_PAGE;

  const match = /^\/v2\/([^/]+)$/.exec(normalizedPath);
  return match && isV2PageKey(match[1]) ? match[1] : V2_DEFAULT_PAGE;
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
