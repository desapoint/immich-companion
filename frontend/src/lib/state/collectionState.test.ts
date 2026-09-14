import { describe, expect, it, vi } from 'vitest';

import {
  collectionHasMore,
  createCollectionController,
  createCollectionState,
} from './collectionState';
import type { PageResult } from '../types/collection';

interface Item { id: string; }

function page(
  items: Item[],
  currentPage = 1,
  pages = 1,
  total = items.length,
  pageSize = 25,
): PageResult<Item> {
  return { items, page: currentPage, pageSize, pages, total };
}

describe('collection state', () => {
  it('distinguishes initial loading from later refreshes', async () => {
    const state = createCollectionState<Item>(25);
    let resolveFirst!: (value: PageResult<Item>) => void;
    const first = new Promise<PageResult<Item>>((resolve) => { resolveFirst = resolve; });
    const loader = vi.fn().mockReturnValueOnce(first).mockResolvedValueOnce(page([{ id: 'b' }]));
    const controller = createCollectionController(state, loader);

    const initial = controller.load();
    expect(state.initialLoading).toBe(true);
    expect(state.refreshing).toBe(false);
    resolveFirst(page([{ id: 'a' }]));
    await initial;

    expect(state.initialLoading).toBe(false);
    expect(state.items).toEqual([{ id: 'a' }]);

    const refresh = controller.reload();
    expect(state.initialLoading).toBe(false);
    expect(state.refreshing).toBe(true);
    await refresh;
    expect(state.refreshing).toBe(false);
    expect(state.items).toEqual([{ id: 'b' }]);
  });

  it('aborts and ignores a superseded request', async () => {
    const state = createCollectionState<Item>(25);
    const pending: Array<{
      signal: AbortSignal;
      resolve: (value: PageResult<Item>) => void;
    }> = [];
    const loader = vi.fn(({ page: requestedPage, signal }: { page: number; signal: AbortSignal }) =>
      new Promise<PageResult<Item>>((resolve) => {
        pending.push({ signal, resolve: (value) => resolve({ ...value, page: requestedPage }) });
      }));
    const controller = createCollectionController(state, loader);

    const first = controller.load(1);
    const second = controller.load(2);
    expect(pending[0].signal.aborted).toBe(true);

    pending[1].resolve(page([{ id: 'new' }], 2, 2, 2));
    await second;
    pending[0].resolve(page([{ id: 'old' }], 1, 2, 2));
    await first;

    expect(state.page).toBe(2);
    expect(state.items).toEqual([{ id: 'new' }]);
  });

  it('keeps usable data when a refresh fails', async () => {
    const state = createCollectionState<Item>(25);
    const loader = vi.fn()
      .mockResolvedValueOnce(page([{ id: 'a' }]))
      .mockRejectedValueOnce(new Error('Refresh failed.'));
    const controller = createCollectionController(state, loader);

    await controller.load();
    await expect(controller.reload()).resolves.toBe(false);

    expect(state.items).toEqual([{ id: 'a' }]);
    expect(state.error).toBe('Refresh failed.');
    expect(state.hasLoaded).toBe(true);
  });

  it('appends and deduplicates the next page by stable key', async () => {
    const state = createCollectionState<Item>(25);
    const loader = vi.fn()
      .mockResolvedValueOnce(page([{ id: 'a' }, { id: 'b' }], 1, 2, 3))
      .mockResolvedValueOnce(page([{ id: 'b' }, { id: 'c' }, { id: 'c' }], 2, 2, 3));
    const controller = createCollectionController(state, loader, { getKey: (item) => item.id });

    await controller.load();
    expect(collectionHasMore(state)).toBe(true);
    await controller.loadNextPage();

    expect(state.items).toEqual([{ id: 'a' }, { id: 'b' }, { id: 'c' }]);
    expect(collectionHasMore(state)).toBe(false);
  });

  it('clamps an out-of-range requested page through a second request', async () => {
    const state = createCollectionState<Item>(25);
    const loader = vi.fn()
      .mockResolvedValueOnce(page([], 4, 2, 30))
      .mockResolvedValueOnce(page([{ id: 'last' }], 2, 2, 30));
    const controller = createCollectionController(state, loader);

    await controller.changePage(4);

    expect(loader.mock.calls.map(([request]) => request.page)).toEqual([4, 2]);
    expect(state.page).toBe(2);
    expect(state.items).toEqual([{ id: 'last' }]);
  });

  it('commits a page-size change only after the new page loads successfully', async () => {
    const state = createCollectionState<Item>(25);
    const loader = vi.fn()
      .mockResolvedValueOnce(page([{ id: 'a' }], 2, 4, 80, 25))
      .mockRejectedValueOnce(new Error('Page-size request failed.'));
    const controller = createCollectionController(state, loader);

    await controller.load(2);
    await expect(controller.changePageSize(50)).resolves.toBe(false);

    expect(loader.mock.calls[1]?.[0]).toMatchObject({ page: 1, pageSize: 50 });
    expect(state.page).toBe(2);
    expect(state.pageSize).toBe(25);
    expect(state.items).toEqual([{ id: 'a' }]);
    expect(state.error).toBe('Page-size request failed.');
  });

  it('does not reload when the requested page size is already active', async () => {
    const state = createCollectionState<Item>(25);
    const loader = vi.fn().mockResolvedValue(page([{ id: 'a' }]));
    const controller = createCollectionController(state, loader);

    await controller.load();
    await expect(controller.changePageSize(25)).resolves.toBe(true);

    expect(loader).toHaveBeenCalledTimes(1);
  });
});
