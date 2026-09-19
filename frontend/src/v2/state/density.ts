export type V2Density = 'standard' | 'condensed';

export const V2_DENSITY_STORAGE_KEY = 'immich-companion-mock-density';
export const V2_DENSITY_EVENT = 'immich-companion-v2-density';

export function readV2Density(): V2Density {
  if (typeof localStorage === 'undefined') return 'standard';
  return localStorage.getItem(V2_DENSITY_STORAGE_KEY) === 'condensed' ? 'condensed' : 'standard';
}

export function writeV2Density(density: V2Density): void {
  localStorage.setItem(V2_DENSITY_STORAGE_KEY, density);
  window.dispatchEvent(new CustomEvent<V2Density>(V2_DENSITY_EVENT, { detail: density }));
}
