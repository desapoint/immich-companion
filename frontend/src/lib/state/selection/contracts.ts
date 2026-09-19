export type SelectionWorkspaceRecord = {
  id: string;
  revision: number;
  selectedCount: number;
  status: 'active' | 'cancelled' | 'expired';
  expiresAt: string;
};

export type SelectionWorkspaceMembership<TWorkspace extends SelectionWorkspaceRecord = SelectionWorkspaceRecord> = {
  selection: TWorkspace;
  selectedIds: string[];
};

export type SelectionWorkspaceTarget = { kind: 'selection'; selectionId: string };

export type SelectionState<T extends string = string> = {
  selectedIds: Set<T>;
  excludedIds: Set<T>;
  allMatchingSelected: boolean;
  anchor: T | null;
};

export type SelectionStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;

export interface SelectionWorkspaceRepository<TCriteria, TWorkspace extends SelectionWorkspaceRecord = SelectionWorkspaceRecord> {
  createSelection(): Promise<TWorkspace>;
  selectAllIntoSelection(selectionId: string, criteria: TCriteria): Promise<TWorkspace>;
  updateMatchingSelection?(selectionId: string, criteria: TCriteria, selected: boolean, revision: number): Promise<TWorkspace>;
  matchingSelectionState?(selectionId: string, criteria: TCriteria): Promise<{ matchingCount: number; selectedMatchingCount: number }>;
  updateSelectionMembers(selectionId: string, ids: readonly string[], selected: boolean, revision: number): Promise<TWorkspace>;
  selectionMembership(selectionId: string, ids: readonly string[]): Promise<SelectionWorkspaceMembership<TWorkspace> | null>;
}
