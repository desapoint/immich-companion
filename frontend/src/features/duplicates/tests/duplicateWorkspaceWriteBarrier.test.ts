import { describe, expect, it, vi } from 'vitest';

import type { DuplicateRepository } from '../types/contracts';
import { withDuplicateWorkspaceWriteBarrier } from '../state/duplicateWorkspaceWriteBarrier';

function deferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function repositoryStub(overrides: Partial<DuplicateRepository>): DuplicateRepository {
  return {
    saveSelection: vi.fn().mockResolvedValue(undefined),
    flushDrafts: vi.fn().mockResolvedValue(undefined),
    clearDecisions: vi.fn().mockResolvedValue(0),
    ...overrides,
  } as unknown as DuplicateRepository;
}

describe('duplicate workspace write barrier', () => {
  it('does not make the UI wait for selection persistence but drains an in-flight write before reset', async () => {
    const selection = deferred<void>();
    const saveSelection = vi.fn(() => selection.promise);
    const clearDecisions = vi.fn().mockResolvedValue(1);
    const repository = repositoryStub({ saveSelection, clearDecisions });
    const guarded = withDuplicateWorkspaceWriteBarrier(repository);

    await expect(guarded.saveSelection(['group-a'], null)).resolves.toBeUndefined();
    await Promise.resolve();
    expect(saveSelection).toHaveBeenCalledWith(['group-a'], null);

    const clearing = guarded.clearDecisions();
    await Promise.resolve();
    expect(clearDecisions).not.toHaveBeenCalled();

    selection.resolve();
    await expect(clearing).resolves.toBe(1);
    expect(clearDecisions).toHaveBeenCalledOnce();
  });

  it('invalidates queued stale selection snapshots when a reset starts', async () => {
    const firstSelection = deferred<void>();
    const saveSelection = vi.fn()
      .mockImplementationOnce(() => firstSelection.promise)
      .mockResolvedValue(undefined);
    const clearDecisions = vi.fn().mockResolvedValue(1);
    const repository = repositoryStub({ saveSelection, clearDecisions });
    const guarded = withDuplicateWorkspaceWriteBarrier(repository);

    await guarded.saveSelection(['group-a'], null);
    await Promise.resolve();
    await guarded.saveSelection(['group-b'], null);

    const clearing = guarded.clearDecisions();
    firstSelection.resolve();
    await clearing;

    expect(saveSelection).toHaveBeenCalledTimes(1);
    expect(saveSelection).toHaveBeenCalledWith(['group-a'], null);
    expect(clearDecisions).toHaveBeenCalledOnce();
  });

  it('surfaces detached selection failures at the next explicit workspace flush', async () => {
    const failure = new Error('selection persistence failed');
    const repository = repositoryStub({
      saveSelection: vi.fn().mockRejectedValue(failure),
      flushDrafts: vi.fn().mockResolvedValue(undefined),
    });
    const guarded = withDuplicateWorkspaceWriteBarrier(repository);

    await expect(guarded.saveSelection(['group-a'], null)).resolves.toBeUndefined();
    await expect(guarded.flushDrafts()).rejects.toBe(failure);
  });

  it('waits for selection persistence before loading a selected-group page', async () => {
    const selection = deferred<void>();
    const saveSelection = vi.fn(() => selection.promise);
    const search = vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, pageSize: 6, nextCursor: null });
    const repository = repositoryStub({ saveSelection, search });
    const guarded = withDuplicateWorkspaceWriteBarrier(repository);

    await guarded.saveSelection(['group-a'], null);
    const loading = guarded.search({ state: 'Selected', page: 1, pageSize: 6 });
    await Promise.resolve();
    expect(search).not.toHaveBeenCalled();

    selection.resolve();
    await expect(loading).resolves.toMatchObject({ total: 0 });
    expect(search).toHaveBeenCalledOnce();
  });
});
