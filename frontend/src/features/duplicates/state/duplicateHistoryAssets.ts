import type { AssetRecord, AssetRepository, TrashAssetRecord } from '../../../lib/types/libraryContracts';
import { errorMessage } from '../../../lib/api/mutationFeedback';

export type DuplicateHistoryAsset = {
  id: string;
  state: 'active' | 'trash' | 'missing' | 'error';
  asset: AssetRecord | TrashAssetRecord | null;
  error: string | null;
};

async function resolveTrashAsset(
  id: string,
  assets: Pick<AssetRepository, 'getTrashById'>,
): Promise<DuplicateHistoryAsset> {
  try {
    const trash = await assets.getTrashById(id);
    if (trash) return { id, state: 'trash', asset: trash, error: null };
    return { id, state: 'missing', asset: null, error: null };
  } catch (error) {
    return {
      id,
      state: 'error',
      asset: null,
      error: errorMessage(error, 'Current asset state could not be loaded.'),
    };
  }
}

export async function resolveDuplicateHistoryAssets(
  ids: readonly string[],
  assets: Pick<AssetRepository, 'getMany' | 'getTrashById'>,
): Promise<DuplicateHistoryAsset[]> {
  const active = await assets.getMany(ids);
  const byId = new Map<string, DuplicateHistoryAsset>(
    active.map((asset) => [asset.id, { id: asset.id, state: 'active', asset, error: null }]),
  );
  const unresolved = [...new Set(ids)].filter((id) => !byId.has(id));
  for (let index = 0; index < unresolved.length; index += 8) {
    const batch = await Promise.all(
      unresolved.slice(index, index + 8).map((id) => resolveTrashAsset(id, assets)),
    );
    for (const item of batch) byId.set(item.id, item);
  }
  return ids.map((id) => byId.get(id) ?? { id, state: 'missing', asset: null, error: null });
}
