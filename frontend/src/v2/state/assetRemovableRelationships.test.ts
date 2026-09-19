import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { AssetSelectionRelationships } from '../data/contracts';

const repositories = vi.hoisted(() => ({ removableRelationships: vi.fn() }));

vi.mock('../data/currentDataSource.svelte', () => ({
  libraryData: { assets: { removableRelationships: repositories.removableRelationships } },
}));

import { AssetRemovableRelationshipsController } from './assetRemovableRelationships.svelte';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

describe('AssetRemovableRelationshipsController', () => {
  beforeEach(() => repositories.removableRelationships.mockReset());

  it('keeps only the newest selection response', async () => {
    const older = deferred<AssetSelectionRelationships>();
    const newer = deferred<AssetSelectionRelationships>();
    repositories.removableRelationships.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const controller = new AssetRemovableRelationshipsController();

    const olderLoad = controller.load({ kind: 'ids', ids: ['old'] });
    const newerLoad = controller.load({ kind: 'ids', ids: ['new'] });
    expect((repositories.removableRelationships.mock.calls[0]?.[1] as AbortSignal).aborted).toBe(true);
    newer.resolve({ albums: [], tags: [{ value: 'new-tag', label: 'New', subtitle: '', selectedAssetCount: 1 }] });
    await newerLoad;
    older.resolve({ albums: [], tags: [{ value: 'old-tag', label: 'Old', subtitle: '', selectedAssetCount: 1 }] });
    await olderLoad;

    expect(controller.tags.map((option) => option.value)).toEqual(['new-tag']);
    expect(controller.loading).toBe(false);
  });
});
