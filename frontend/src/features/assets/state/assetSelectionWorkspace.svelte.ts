import type { AssetSearchCriteria, AssetSelectionWorkspace } from '../../../lib/types/libraryContracts';
import {
  SelectionWorkspaceController,
  type SelectionWorkspaceRepository,
} from '../../../lib/state/selectionWorkspace.svelte';

export type AssetSelectionWorkspaceRepository = SelectionWorkspaceRepository<AssetSearchCriteria, AssetSelectionWorkspace>;

export class AssetSelectionWorkspaceController extends SelectionWorkspaceController<AssetSearchCriteria, AssetSelectionWorkspace> {
  constructor(
    repository: AssetSelectionWorkspaceRepository,
    storage?: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'> | null,
  ) {
    super(repository, storage, 'immich-companion:v2:asset-selection');
  }
}
