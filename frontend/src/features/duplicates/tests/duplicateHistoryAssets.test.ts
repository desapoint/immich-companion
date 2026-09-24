import { describe, expect, it, vi } from 'vitest';

import type { AssetRecord, AssetRepository, TrashAssetRecord } from '../../../lib/types/libraryContracts';
import { resolveDuplicateHistoryAssets } from '../state/duplicateHistoryAssets';

const active = { id: 'active', original_file_name: 'active.jpg' } as AssetRecord;
const trash = { id: 'trash', original_file_name: 'trash.jpg' } as TrashAssetRecord;

describe('duplicate history asset resolution', () => {
  it('loads active summaries once and probes trash only for unresolved IDs', async () => {
    const assets = {
      getMany: vi.fn(async () => [active]),
      getTrashById: vi.fn(async (id: string) => id === 'trash' ? trash : undefined),
    } as unknown as Pick<AssetRepository, 'getMany' | 'getTrashById'>;

    const result = await resolveDuplicateHistoryAssets(['active', 'trash', 'missing'], assets);

    expect(assets.getMany).toHaveBeenCalledOnce();
    expect(assets.getMany).toHaveBeenCalledWith(['active', 'trash', 'missing']);
    expect(assets.getTrashById).toHaveBeenCalledTimes(2);
    expect(assets.getTrashById).not.toHaveBeenCalledWith('active');
    expect(result.map((item) => item.state)).toEqual(['active', 'trash', 'missing']);
  });
});
