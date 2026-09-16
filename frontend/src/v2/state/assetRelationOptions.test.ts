import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { OptionSearchResult } from '../data/contracts';

const repositories = vi.hoisted(() => ({
  searchAlbums: vi.fn(),
  searchTags: vi.fn(),
}));

vi.mock('../data/currentDataSource.svelte', () => ({
  libraryData: {
    albums: { searchOptions: repositories.searchAlbums },
    tags: { searchOptions: repositories.searchTags },
  },
}));

import { AssetRelationOptionsController } from './assetRelationOptions.svelte';

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

const emptyResult: OptionSearchResult = { items: [], nextCursor: null };

describe('AssetRelationOptionsController request races', () => {
  beforeEach(() => {
    repositories.searchAlbums.mockReset();
    repositories.searchTags.mockReset();
  });

  it('aborts and ignores an older album option response', async () => {
    const older = deferred<OptionSearchResult>();
    const newer = deferred<OptionSearchResult>();
    repositories.searchAlbums.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const controller = new AssetRelationOptionsController();

    const olderSearch = controller.searchAlbums('old', []);
    const newerSearch = controller.searchAlbums('new', []);

    const olderSignal = repositories.searchAlbums.mock.calls[0]?.[0].signal as AbortSignal;
    expect(olderSignal.aborted).toBe(true);
    newer.resolve({ items: [{ value: 'new', label: 'New', subtitle: '' }], nextCursor: null });
    await newerSearch;
    older.resolve({ items: [{ value: 'old', label: 'Old', subtitle: '' }], nextCursor: null });
    await olderSearch;

    expect(controller.albumOptions.map((option) => option.value)).toEqual(['new']);
    expect(controller.albumLoading).toBe(false);
  });

  it('aborts and ignores an older tag option response', async () => {
    const older = deferred<OptionSearchResult>();
    const newer = deferred<OptionSearchResult>();
    repositories.searchTags.mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const controller = new AssetRelationOptionsController();

    const olderSearch = controller.searchTags('old', []);
    const newerSearch = controller.searchTags('new', []);

    const olderSignal = repositories.searchTags.mock.calls[0]?.[0].signal as AbortSignal;
    expect(olderSignal.aborted).toBe(true);
    newer.resolve({ items: [{ value: 'new', label: 'New', subtitle: '' }], nextCursor: null });
    await newerSearch;
    older.resolve({ items: [{ value: 'old', label: 'Old', subtitle: '' }], nextCursor: null });
    await olderSearch;

    expect(controller.tagOptions.map((option) => option.value)).toEqual(['new']);
    expect(controller.tagLoading).toBe(false);
  });

  it('does not let one relation request hide the other relation error', async () => {
    repositories.searchAlbums.mockRejectedValueOnce(new Error('Albums offline'));
    repositories.searchTags.mockResolvedValueOnce(emptyResult);
    const controller = new AssetRelationOptionsController();

    await Promise.all([
      controller.searchAlbums('', []),
      controller.searchTags('', []),
    ]);

    expect(controller.error).toBe('Albums offline');
  });
});
