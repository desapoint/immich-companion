export type V2Density = 'standard' | 'condensed';

/** The V2 shell uses one deliberate, compact density. Kept as a compatibility
 * type/API for settings integrations while density controls are retired. */
export const V2_DENSITY_STORAGE_KEY = 'immich-companion-mock-density';
export const V2_DENSITY_EVENT = 'immich-companion-v2-density';

export function readV2Density(): V2Density {
  return 'condensed';
}

export function writeV2Density(_density: V2Density): void {}
