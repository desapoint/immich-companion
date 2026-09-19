import {
  DEFAULT_SELECTION_STORAGE_KEY,
  MEMBER_BATCH_SIZE,
  WRITE_DEBOUNCE_MS,
} from './selection/constants';
import type {
  SelectionState,
  SelectionStorage,
  SelectionWorkspaceMembership,
  SelectionWorkspaceRecord,
  SelectionWorkspaceRepository,
  SelectionWorkspaceTarget,
} from './selection/contracts';
import { applyMembership, visibleAnchor } from './selection/helpers';
import { readVisibleMembership } from './selection/membership';
import { clearSelectionId, defaultSelectionStorage, persistSelectionId, readSelectionId } from './selection/storage';

export type {
  SelectionState,
  SelectionStorage,
  SelectionWorkspaceMembership,
  SelectionWorkspaceRecord,
  SelectionWorkspaceRepository,
  SelectionWorkspaceTarget,
} from './selection/contracts';

export class SelectionWorkspaceController<TCriteria, TWorkspace extends SelectionWorkspaceRecord = SelectionWorkspaceRecord> {
  selectionId = $state<string | null>(null);
  revision = $state<number | null>(null);
  serverSelectedCount = $state(0);
  visibleSelectedIds = $state<Set<string>>(new Set());
  anchor = $state<string | null>(null);
  allMatchingSelected = $state(false);
  matchingSelectedCount = $state(0);
  matchingTotal = $state(0);
  error = $state('');

  private readonly serverVisibleIds = new Set<string>();
  private readonly visibleAssetIds = new Set<string>();
  private readonly pending = new Map<string, boolean>();
  private pendingVersion = $state(0);
  private timer: ReturnType<typeof setTimeout> | null = null;
  private writeChain: Promise<void> = Promise.resolve();
  private workspacePromise: Promise<TWorkspace> | null = null;
  private generation = 0;

  constructor(
    private readonly repository: SelectionWorkspaceRepository<TCriteria, TWorkspace>,
    private readonly storage: SelectionStorage | null = defaultSelectionStorage(),
    private readonly storageKey = DEFAULT_SELECTION_STORAGE_KEY,
  ) {
    this.selectionId = readSelectionId(this.storage, this.storageKey);
  }

  get selectedCount(): number {
    void this.pendingVersion;
    let count = this.serverSelectedCount;
    for (const [id, selected] of this.pending) {
      const wasSelected = this.serverVisibleIds.has(id);
      if (selected && !wasSelected) count += 1;
      else if (!selected && wasSelected) count -= 1;
    }
    return Math.max(0, count);
  }

  get active(): boolean { return this.selectedCount > 0; }

  snapshot(): SelectionState<string> {
    return {
      selectedIds: new Set(this.visibleSelectedIds),
      excludedIds: new Set(),
      // The database already contains an exact snapshot. The all-matching flag
      // is display metadata only and must not make visible toggles query-based.
      allMatchingSelected: false,
      anchor: this.anchor,
    };
  }

  replaceVisible(next: SelectionState<string>): void {
    const ids = new Set([...this.visibleSelectedIds, ...next.selectedIds]);
    for (const id of ids) {
      const selected = next.selectedIds.has(id);
      if (this.visibleSelectedIds.has(id) !== selected) this.stageMember(id, selected);
    }
    this.visibleSelectedIds = new Set(next.selectedIds);
    this.anchor = next.anchor;
    this.allMatchingSelected = false;
    this.pendingVersion += 1;
    this.scheduleFlush();
  }

  setMembers(assetIds: readonly string[], selected: boolean, anchor: string | null = this.anchor): void {
    const next = new Set(this.visibleSelectedIds);
    for (const id of assetIds) {
      this.visibleAssetIds.add(id);
      if (next.has(id) === selected) continue;
      if (selected) next.add(id); else next.delete(id);
      this.stageMember(id, selected);
    }
    this.visibleSelectedIds = next;
    this.anchor = anchor;
    this.allMatchingSelected = false;
    this.pendingVersion += 1;
    this.scheduleFlush();
  }

  async refreshVisible(assetIds: readonly string[]): Promise<void> {
    await this.flush();
    this.visibleAssetIds.clear();
    assetIds.forEach((id) => this.visibleAssetIds.add(id));
    if (!this.selectionId) {
      this.applyEmptyVisible();
      return;
    }
    const selectionId = this.selectionId;
    const operation = this.writeChain.then(async () => {
      const membership = await readVisibleMembership(this.repository, selectionId, assetIds);
      if (!membership) {
        this.abandon();
        return;
      }
      if (this.selectionId !== selectionId) return;
      const { workspace, selectedIds } = membership;
      this.applyWorkspace(workspace);
      this.serverVisibleIds.clear();
      selectedIds.forEach((id) => this.serverVisibleIds.add(id));
      const visible = new Set(selectedIds);
      // Changes made while membership was loading stay optimistic and will be
      // written after this read in the same serialized queue.
      for (const [id, selected] of this.pending) {
        if (!assetIds.includes(id)) continue;
        if (selected) visible.add(id); else visible.delete(id);
      }
      this.visibleSelectedIds = visible;
      this.anchor = visibleAnchor(visible, this.anchor);
      this.allMatchingSelected = false;
      this.pendingVersion += 1;
    });
    this.writeChain = operation.catch(() => {});
    await operation;
  }

  async selectAll(criteria: TCriteria, visibleIds: readonly string[], matchingTotal: number): Promise<void> {
    this.cancelTimer();
    this.pending.clear();
    this.visibleSelectedIds = new Set(visibleIds);
    this.serverSelectedCount = matchingTotal;
    this.anchor = visibleIds[0] ?? null;
    this.allMatchingSelected = true;
    this.pendingVersion += 1;
    const generation = this.generation;
    const operation = this.writeChain.then(async () => {
      if (generation !== this.generation) return;
      const workspace = await this.ensureWorkspace();
      const selected = await this.repository.selectAllIntoSelection(workspace.id, criteria);
      if (generation !== this.generation) return;
      this.applyWorkspace(selected);
      this.serverVisibleIds.clear();
      visibleIds.forEach((id) => this.serverVisibleIds.add(id));
      await this.drainPending();
    });
    this.writeChain = operation.catch(() => {});
    await operation;
  }

  async setMatching(criteria: TCriteria, visibleIds: readonly string[], selected: boolean): Promise<void> {
    const updateMatching = this.repository.updateMatchingSelection;
    if (!updateMatching) throw new Error('Matching selection updates are unavailable.');
    const previousVisible = new Set(this.visibleSelectedIds);
    const visible = new Set(this.visibleSelectedIds);
    for (const id of visibleIds) {
      if (selected) visible.add(id); else visible.delete(id);
    }
    this.visibleSelectedIds = visible;
    this.anchor = selected ? visibleIds[0] ?? this.anchor : null;
    this.allMatchingSelected = selected;
    this.matchingSelectedCount = selected ? this.matchingTotal : 0;
    this.pendingVersion += 1;
    try {
      await this.flush();
      const generation = this.generation;
      const operation = this.writeChain.then(async () => {
        if (generation !== this.generation) return;
        const workspace = await this.ensureWorkspace();
        if (generation !== this.generation) return;
        let updated: TWorkspace;
        try {
          updated = await updateMatching(workspace.id, criteria, selected, workspace.revision);
        } catch (error) {
          const membership = await this.repository.selectionMembership(workspace.id, []);
          if (!membership || membership.selection.status !== 'active') throw error;
          this.applyWorkspace(membership.selection);
          updated = await updateMatching(workspace.id, criteria, selected, membership.selection.revision);
        }
        if (generation !== this.generation) return;
        this.applyWorkspace(updated);
        for (const id of visibleIds) {
          if (selected) this.serverVisibleIds.add(id); else this.serverVisibleIds.delete(id);
        }
      });
      this.writeChain = operation.catch(() => {});
      await operation;
    } catch (error) {
      this.visibleSelectedIds = previousVisible;
      this.allMatchingSelected = false;
      this.pendingVersion += 1;
      this.error = error instanceof Error ? error.message : 'Matching selection could not be saved.';
      throw error;
    }
  }

  async refreshMatching(criteria: TCriteria): Promise<void> {
    if (!this.selectionId || !this.repository.matchingSelectionState) {
      this.allMatchingSelected = false;
      this.matchingSelectedCount = 0;
      this.matchingTotal = 0;
      return;
    }
    const selectionId = this.selectionId;
    const state = await this.repository.matchingSelectionState(selectionId, criteria);
    if (this.selectionId !== selectionId) return;
    this.matchingTotal = state.matchingCount;
    this.matchingSelectedCount = state.selectedMatchingCount;
    this.allMatchingSelected = state.matchingCount > 0
      && state.selectedMatchingCount === state.matchingCount;
  }

  async flush(): Promise<void> {
    this.cancelTimer();
    const operation = this.writeChain.then(() => this.drainPending());
    this.writeChain = operation.catch(() => {});
    await operation;
  }

  async target(): Promise<SelectionWorkspaceTarget> {
    await this.flush();
    if (!this.selectionId || this.serverSelectedCount === 0) throw new Error('No assets are selected.');
    const selectionId = this.selectionId;
    const membership = await this.repository.selectionMembership(selectionId, []);
    if (!membership || membership.selection.status !== 'active') {
      this.abandon();
      throw new Error('The saved selection expired. Select the assets again.');
    }
    this.applyWorkspace(membership.selection);
    if (membership.selection.selectedCount === 0) throw new Error('No assets are selected.');
    return { kind: 'selection', selectionId };
  }

  clear(): void { this.abandon(); }

  abandon(): void {
    this.generation += 1;
    this.cancelTimer();
    this.pending.clear();
    this.workspacePromise = null;
    this.selectionId = null;
    this.revision = null;
    this.serverSelectedCount = 0;
    clearSelectionId(this.storage, this.storageKey);
    this.applyEmptyVisible();
  }

  private applyEmptyVisible(): void {
    this.serverVisibleIds.clear();
    this.visibleAssetIds.clear();
    this.visibleSelectedIds = new Set();
    this.anchor = null;
    this.allMatchingSelected = false;
    this.matchingSelectedCount = 0;
    this.matchingTotal = 0;
    this.pendingVersion += 1;
  }

  private applyWorkspace(workspace: TWorkspace): void {
    this.selectionId = workspace.id;
    this.revision = workspace.revision;
    this.serverSelectedCount = workspace.selectedCount;
    persistSelectionId(this.storage, this.storageKey, workspace.id);
    this.error = '';
  }

  private async ensureWorkspace(): Promise<TWorkspace> {
    if (this.selectionId && this.revision !== null) {
      return {
        id: this.selectionId,
        revision: this.revision,
        selectedCount: this.serverSelectedCount,
        status: 'active',
        expiresAt: '',
      } as TWorkspace;
    }
    if (!this.workspacePromise) {
      const generation = this.generation;
      const pending = this.repository.createSelection().then((workspace) => {
        if (generation === this.generation) this.applyWorkspace(workspace);
        return workspace;
      }).finally(() => { if (this.workspacePromise === pending) this.workspacePromise = null; });
      this.workspacePromise = pending;
    }
    return this.workspacePromise;
  }

  private scheduleFlush(): void {
    this.cancelTimer();
    this.timer = setTimeout(() => { void this.flush().catch((error) => { this.error = error instanceof Error ? error.message : 'Selection could not be saved.'; }); }, WRITE_DEBOUNCE_MS);
  }

  private stageMember(id: string, selected: boolean): void {
    if (this.serverVisibleIds.has(id) === selected) this.pending.delete(id);
    else this.pending.set(id, selected);
  }

  private cancelTimer(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
  }

  private async drainPending(allowRecovery = true): Promise<void> {
    while (this.pending.size) {
      const first = this.pending.entries().next().value as [string, boolean] | undefined;
      if (!first) return;
      const selected = first[1];
      const batch: Array<[string, boolean]> = [];
      for (const entry of this.pending) {
        if (entry[1] === selected) batch.push(entry);
        if (batch.length >= MEMBER_BATCH_SIZE) break;
      }
      for (const [id] of batch) this.pending.delete(id);
      this.pendingVersion += 1;
      const before = new Map(batch.map(([id]) => [id, this.serverVisibleIds.has(id)]));
      const generation = this.generation;
      const optimisticCountDelta = applyMembership(this.serverVisibleIds, batch.map(([id]) => id), selected);
      this.serverSelectedCount = Math.max(0, this.serverSelectedCount + optimisticCountDelta);
      let workspace: TWorkspace | null = null;
      try {
        workspace = await this.ensureWorkspace();
        const updated = await this.repository.updateSelectionMembers(workspace.id, batch.map(([id]) => id), selected, workspace.revision);
        if (generation !== this.generation) return;
        this.applyWorkspace(updated);
      } catch (error) {
        if (generation !== this.generation) return;
        this.serverSelectedCount = Math.max(0, this.serverSelectedCount - optimisticCountDelta);
        for (const [id] of batch) {
          if (before.get(id)) this.serverVisibleIds.add(id); else this.serverVisibleIds.delete(id);
          if (!this.pending.has(id)) this.pending.set(id, selected);
        }
        this.pendingVersion += 1;
        if (allowRecovery && workspace && await this.recoverAfterWriteFailure(workspace.id)) {
          await this.drainPending(false);
          return;
        }
        throw error;
      }
    }
  }

  private async recoverAfterWriteFailure(selectionId: string): Promise<boolean> {
    try {
      const assetIds = [...this.visibleAssetIds];
      const membership = await readVisibleMembership(this.repository, selectionId, assetIds);
      if (!membership) {
        this.abandon();
        throw new Error('The saved selection expired. Select the assets again.');
      }
      if (this.selectionId !== selectionId) return false;
      const { workspace, selectedIds } = membership;
      this.applyWorkspace(workspace);
      this.serverVisibleIds.clear();
      selectedIds.forEach((id) => this.serverVisibleIds.add(id));
      for (const [id, desired] of [...this.pending]) {
        if (this.serverVisibleIds.has(id) === desired) this.pending.delete(id);
      }
      const visible = new Set(this.serverVisibleIds);
      for (const [id, desired] of this.pending) {
        if (desired) visible.add(id); else visible.delete(id);
      }
      this.visibleSelectedIds = visible;
      this.anchor = visibleAnchor(visible, this.anchor);
      this.pendingVersion += 1;
      return true;
    } catch (error) {
      if (!this.selectionId) throw error;
      return false;
    }
  }
}
