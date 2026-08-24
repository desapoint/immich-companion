import type { AssetSort } from '../types/assets';

export function createDefaultAssetSort(): AssetSort {
  return { field: 'taken_at', direction: 'desc' };
}
