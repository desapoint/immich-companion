import type { LiveLibraryDataSource } from '../liveContracts';
import { withDuplicateStackConflictReview } from '../duplicateStackConflictReviewRepository';
import { createAlbumRepository } from './albumRepository';
import { createAssetApiProfile } from './assetRepository';
import { createDuplicateRepository } from '../../../features/duplicates/api/duplicateRepository';
import { createLocalSavedSearchRepository } from './localSavedSearchRepository';
import { createSyncRepository } from './syncRepository';
import { createTagRepository } from './tagRepository';
import { createTaskRepository } from './taskRepository';

/**
 * Production V2 data source.
 *
 * A backend endpoint existing is not enough to make a V2 action live; every operation
 * is explicitly adapted through a V2 repository boundary here.
 */
export function createApiLibraryDataSource(): LiveLibraryDataSource {
  const assetProfile = createAssetApiProfile();
  const tasks = createTaskRepository();
  const duplicates = withDuplicateStackConflictReview(createDuplicateRepository(tasks), assetProfile.assets);
  return {
    kind: 'api',
    initialize: async () => undefined,
    assets: assetProfile.assets,
    albums: createAlbumRepository(),
    tags: createTagRepository(),
    savedSearches: createLocalSavedSearchRepository(),
    duplicates,
    media: assetProfile.media,
    navigation: assetProfile.navigation,
    sync: createSyncRepository(),
    tasks,
  };
}
