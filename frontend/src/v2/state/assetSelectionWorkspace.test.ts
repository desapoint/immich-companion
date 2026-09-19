import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AssetRepository, AssetSelectionWorkspace } from '../data/contracts';
import { AssetSelectionWorkspaceController, SelectionWorkspaceController, type SelectionWorkspaceRepository } from './assetSelectionWorkspace.svelte';

const active = (revision = 0, selectedCount = 0): AssetSelectionWorkspace => ({
  id: 'selection-1', revision, selectedCount, status: 'active', expiresAt: '2099-01-01T00:00:00Z',
});

function fixture() {
  let revision = 0;
  const selected = new Set<string>();
  const repository = {
    createSelection: vi.fn(async () => active(revision, selected.size)),
    updateSelectionMembers: vi.fn(async (_id: string, ids: readonly string[], value: boolean, expectedRevision: number) => {
      expect(expectedRevision).toBe(revision);
      ids.forEach((id) => value ? selected.add(id) : selected.delete(id));
      revision += 1;
      return active(revision, selected.size);
    }),
    selectAllIntoSelection: vi.fn(async () => active(++revision, selected.size)),
    selectionMembership: vi.fn(async (_id: string, ids: readonly string[]) => ({ selection: active(revision, selected.size), selectedIds: ids.filter((id) => selected.has(id)) })),
  } as unknown as AssetRepository;
  const values = new Map<string, string>();
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  };
  return { repository, selected, storage };
}

afterEach(() => vi.useRealTimers());

describe('V2 database-backed asset selection workspace', () => {
  it('adds and removes matching relations without dropping an off-filter selection', async () => {
    const { repository, selected, storage } = fixture();
    selected.add('outside');
    storage.setItem('immich-companion:v2:tag-selection', 'selection-1');
    const updateMatchingSelection = vi.fn(async (_id: string, criteria: { query: string }, value: boolean, revision: number) => {
      expect(criteria).toEqual({ query: 'inside' });
      expect(revision).toBeGreaterThanOrEqual(0);
      for (const id of ['inside-1', 'inside-2']) {
        if (value) selected.add(id); else selected.delete(id);
      }
      return active(revision + 1, selected.size);
    });
    const controller = new SelectionWorkspaceController<{ query: string }>(
      { ...repository, updateMatchingSelection } as unknown as SelectionWorkspaceRepository<{ query: string }>,
      storage, 'immich-companion:v2:tag-selection',
    );
    await controller.refreshVisible(['inside-1']);

    await controller.setMatching({ query: 'inside' }, ['inside-1'], true);
    expect([...selected].sort()).toEqual(['inside-1', 'inside-2', 'outside']);
    expect(controller.selectedCount).toBe(3);
    await controller.setMatching({ query: 'inside' }, ['inside-1'], false);
    expect([...selected]).toEqual(['outside']);
    expect(controller.selectedCount).toBe(1);
  });

  it('updates visible state immediately and debounces member writes', async () => {
    vi.useFakeTimers();
    const { repository, storage } = fixture();
    const controller = new AssetSelectionWorkspaceController(repository, storage);

    controller.setMembers(['a'], true, 'a');
    controller.setMembers(['b'], true, 'b');

    expect([...controller.visibleSelectedIds]).toEqual(['a', 'b']);
    expect(controller.selectedCount).toBe(2);
    expect(repository.createSelection).not.toHaveBeenCalled();
    expect(repository.updateSelectionMembers).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(180);
    await controller.flush();

    expect(repository.createSelection).toHaveBeenCalledTimes(1);
    expect(repository.updateSelectionMembers).toHaveBeenCalledWith('selection-1', ['a', 'b'], true, 0);
    expect(controller.selectedCount).toBe(2);
  });

  it('flushes pending member writes before producing a bulk-action target', async () => {
    vi.useFakeTimers();
    const { repository, storage } = fixture();
    const controller = new AssetSelectionWorkspaceController(repository, storage);
    controller.setMembers(['a'], true);

    await expect(controller.target()).resolves.toEqual({ kind: 'selection', selectionId: 'selection-1' });
    expect(repository.updateSelectionMembers).toHaveBeenCalledTimes(1);
  });

  it('uses database membership directly when reattaching a stored workspace', async () => {
    const { repository, selected, storage } = fixture();
    selected.add('b');
    storage.setItem('immich-companion:v2:asset-selection', 'selection-1');
    const controller = new AssetSelectionWorkspaceController(repository, storage);

    await controller.refreshVisible(['a', 'b', 'c']);

    expect([...controller.visibleSelectedIds]).toEqual(['b']);
    expect(repository.selectionMembership).toHaveBeenCalledWith('selection-1', ['a', 'b', 'c']);
    expect(repository.createSelection).not.toHaveBeenCalled();
    expect(repository.updateSelectionMembers).not.toHaveBeenCalled();
  });

  it('loads large visible membership in bounded database requests', async () => {
    const { repository, selected, storage } = fixture();
    const ids = Array.from({ length: 2_001 }, (_, index) => `asset-${index}`);
    selected.add(ids[0]!);
    selected.add(ids[2_000]!);
    storage.setItem('immich-companion:v2:asset-selection', 'selection-1');
    const controller = new AssetSelectionWorkspaceController(repository, storage);

    await controller.refreshVisible(ids);

    expect(repository.selectionMembership).toHaveBeenCalledTimes(2);
    expect([...controller.visibleSelectedIds]).toEqual([ids[0], ids[2_000]]);
  });

  it('does not create a workspace when optimistic changes cancel before the debounce', async () => {
    vi.useFakeTimers();
    const { repository, storage } = fixture();
    const controller = new AssetSelectionWorkspaceController(repository, storage);
    controller.setMembers(['a'], true);
    controller.setMembers(['a'], false);

    await vi.advanceTimersByTimeAsync(180);
    await controller.flush();

    expect(repository.createSelection).not.toHaveBeenCalled();
    expect(controller.selectedCount).toBe(0);
  });

  it('keeps interaction made while database membership is loading', async () => {
    let resolveMembership!: (value: Awaited<ReturnType<AssetRepository['selectionMembership']>>) => void;
    const { repository, storage } = fixture();
    repository.selectionMembership = vi.fn(() => new Promise<Awaited<ReturnType<AssetRepository['selectionMembership']>>>((resolve) => { resolveMembership = resolve; }));
    storage.setItem('immich-companion:v2:asset-selection', 'selection-1');
    const controller = new AssetSelectionWorkspaceController(repository, storage);

    const loading = controller.refreshVisible(['a', 'b']);
    await vi.waitFor(() => expect(repository.selectionMembership).toHaveBeenCalled());
    controller.setMembers(['b'], true);
    resolveMembership({ selection: active(), selectedIds: ['a'] });
    await loading;

    expect([...controller.visibleSelectedIds]).toEqual(['a', 'b']);
    await controller.flush();
    expect(repository.updateSelectionMembers).toHaveBeenCalledWith('selection-1', ['b'], true, 0);
  });

  it('does not resurrect a workspace cleared during an in-flight write', async () => {
    let resolveCreate!: (value: AssetSelectionWorkspace) => void;
    const { repository, storage } = fixture();
    repository.createSelection = vi.fn(() => new Promise<AssetSelectionWorkspace>((resolve) => { resolveCreate = resolve; }));
    const controller = new AssetSelectionWorkspaceController(repository, storage);
    controller.setMembers(['a'], true);

    const flushing = controller.flush();
    await vi.waitFor(() => expect(repository.createSelection).toHaveBeenCalled());
    controller.clear();
    resolveCreate(active());
    await flushing;

    expect(controller.selectionId).toBeNull();
    expect(controller.selectedCount).toBe(0);
  });

  it('abandons a stored selection that expires before a bulk action', async () => {
    const { repository, selected, storage } = fixture();
    selected.add('a');
    storage.setItem('immich-companion:v2:asset-selection', 'selection-1');
    const controller = new AssetSelectionWorkspaceController(repository, storage);
    await controller.refreshVisible(['a']);
    repository.selectionMembership = vi.fn(async () => null);

    await expect(controller.target()).rejects.toThrow('saved selection expired');
    expect(controller.selectionId).toBeNull();
    expect(controller.selectedCount).toBe(0);
  });

  it('recovers a revision conflict from authoritative membership and retries once', async () => {
    const { repository, selected, storage } = fixture();
    let revision = 1;
    storage.setItem('immich-companion:v2:asset-selection', 'selection-1');
    repository.selectionMembership = vi.fn(async (_id: string, ids: readonly string[]) => ({
      selection: active(revision, selected.size),
      selectedIds: ids.filter((id) => selected.has(id)),
    }));
    repository.updateSelectionMembers = vi.fn(async (_id: string, ids: readonly string[], value: boolean, expectedRevision: number) => {
      if (expectedRevision === 0) throw new Error('Selection revision conflict');
      expect(expectedRevision).toBe(1);
      ids.forEach((id) => value ? selected.add(id) : selected.delete(id));
      revision += 1;
      return active(revision, selected.size);
    });
    const controller = new AssetSelectionWorkspaceController(repository, storage);
    await controller.refreshVisible(['a']);
    controller.revision = 0;
    controller.setMembers(['a'], true);

    await controller.flush();

    expect(repository.updateSelectionMembers).toHaveBeenCalledTimes(2);
    expect(controller.selectedCount).toBe(1);
    expect(controller.error).toBe('');
  });

  it('does not repeat a write whose response was lost after the server applied it', async () => {
    const { repository, selected, storage } = fixture();
    let revision = 0;
    repository.updateSelectionMembers = vi.fn(async (_id: string, ids: readonly string[], value: boolean) => {
      ids.forEach((id) => value ? selected.add(id) : selected.delete(id));
      revision += 1;
      throw new Error('Connection closed after write');
    });
    repository.selectionMembership = vi.fn(async (_id: string, ids: readonly string[]) => ({
      selection: active(revision, selected.size),
      selectedIds: ids.filter((id) => selected.has(id)),
    }));
    const controller = new AssetSelectionWorkspaceController(repository, storage);
    controller.setMembers(['a'], true);

    await controller.flush();

    expect(repository.updateSelectionMembers).toHaveBeenCalledTimes(1);
    expect(controller.selectedCount).toBe(1);
    await expect(controller.target()).resolves.toEqual({ kind: 'selection', selectionId: 'selection-1' });
  });
});
