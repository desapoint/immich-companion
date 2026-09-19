import { libraryData } from '../../../app/data/currentDataSource.svelte';
import type { DuplicateDecision, DuplicateGroupRecord, DuplicateResolutionPlan } from '../types/contracts';
import {
  assignAssetToActiveStack,
  createDuplicateStackWorkspace,
  createPendingStack,
  removeAssetFromPendingStack,
  setPendingStackPrimary,
  type DuplicateStackWorkspace,
} from '../../../v2/state/duplicateStackResolution';

export class DuplicatePagePersistence {
  readonly draftTimers = new Map<string, ReturnType<typeof setTimeout>>();
  private selectionSave = Promise.resolve();
  private workspaceHydrated = false;

  hydrateWorkspace(
    items: DuplicateGroupRecord[],
    replace: boolean,
    decisions: Record<string, DuplicateDecision>,
    stackWorkspace: DuplicateStackWorkspace,
    selectedGroups: string[],
  ): { decisions: Record<string, DuplicateDecision>; stackWorkspace: DuplicateStackWorkspace; selectedGroups: string[] } {
    let nextDecisions = replace ? {} : { ...decisions };
    let nextStacks = replace ? createDuplicateStackWorkspace() : stackWorkspace;
    const selected = replace ? [...libraryData.duplicates.selectedGroupIds()] : [...selectedGroups];
    for (const item of items) {
      nextDecisions = { ...nextDecisions, ...item.savedDecisions };
      if (item.selected && !selected.includes(item.id)) selected.push(item.id);
      const stackIds = item.members.filter((entry) => item.savedDecisions[entry.asset.id] === 'stack').map((entry) => entry.asset.id);
      if (stackIds.length) {
        nextStacks = createPendingStack(nextStacks, item.id);
        for (const id of stackIds) nextStacks = assignAssetToActiveStack(nextStacks, item.id, id);
        if (item.stackPrimaryAssetId) nextStacks = setPendingStackPrimary(nextStacks, item.stackPrimaryAssetId);
      }
    }
    this.workspaceHydrated = true;
    return { decisions: nextDecisions, stackWorkspace: nextStacks, selectedGroups: selected };
  }

  async flushWorkspace(groups: DuplicateGroupRecord[], groupResolution: (item: DuplicateGroupRecord) => DuplicateResolutionPlan): Promise<void> {
    const writes: Promise<void>[] = [];
    for (const item of groups) {
      const timer = this.draftTimers.get(item.id);
      if (!timer) continue;
      clearTimeout(timer);
      this.draftTimers.delete(item.id);
      writes.push(libraryData.duplicates.saveDraft(item.id, groupResolution(item)));
    }
    await Promise.all(writes);
    await libraryData.duplicates.flushDrafts();
    await this.selectionSave;
  }

  scheduleDraft(item: DuplicateGroupRecord, groupResolution: () => DuplicateResolutionPlan, onError: (error: unknown) => void): void {
    const previous = this.draftTimers.get(item.id);
    if (previous) clearTimeout(previous);
    this.draftTimers.set(item.id, setTimeout(() => {
      this.draftTimers.delete(item.id);
      const resolution = groupResolution();
      if (!Object.keys(resolution.decisions).length) return;
      void libraryData.duplicates.saveDraft(item.id, resolution).catch(onError);
    }, 250));
  }

  cancelDraft(id: string): void {
    const timer = this.draftTimers.get(id);
    if (timer) clearTimeout(timer);
    this.draftTimers.delete(id);
  }

  async waitForSelectionSave(): Promise<void> { await this.selectionSave.catch(() => undefined); }

  persistSelection(selectedGroups: string[], activeGroup: string | null, onError: (error: unknown) => void): void {
    if (!this.workspaceHydrated) return;
    this.selectionSave = this.selectionSave.catch(() => undefined).then(() => libraryData.duplicates.saveSelection([...selectedGroups], activeGroup)).catch(onError);
  }

  dispose(): void {
    for (const timer of this.draftTimers.values()) clearTimeout(timer);
    this.draftTimers.clear();
  }
}
