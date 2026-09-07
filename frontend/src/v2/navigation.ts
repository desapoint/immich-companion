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

export const V2_DEFAULT_PAGE: V2PageKey = 'settings';

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
