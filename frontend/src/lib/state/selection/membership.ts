import type { SelectionWorkspaceRecord, SelectionWorkspaceRepository } from './contracts';
import { batchIds } from './helpers';

export type VisibleMembership<TWorkspace extends SelectionWorkspaceRecord> = {
  workspace: TWorkspace;
  selectedIds: string[];
};

export async function readVisibleMembership<TCriteria, TWorkspace extends SelectionWorkspaceRecord>(
  repository: SelectionWorkspaceRepository<TCriteria, TWorkspace>,
  selectionId: string,
  assetIds: readonly string[],
): Promise<VisibleMembership<TWorkspace> | null> {
  const selectedIds: string[] = [];
  let workspace: TWorkspace | null = null;
  for (const batch of batchIds(assetIds)) {
    const membership = await repository.selectionMembership(selectionId, batch);
    if (!membership || membership.selection.status !== 'active') return null;
    workspace = membership.selection;
    selectedIds.push(...membership.selectedIds);
  }
  return workspace ? { workspace, selectedIds } : null;
}
