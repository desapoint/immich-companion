import type { LiveLibraryDataSource } from './liveContracts';
import { withDuplicateStackConflictReview } from '../../features/duplicates/api/duplicateStackConflictReviewRepository';
import { createAlbumRepository } from '../../features/albums/api/albumRepository';
import { createAssetApiProfile } from '../../features/assets/api/assetRepository';
import { createDuplicateRepository } from '../../features/duplicates/api/duplicateRepository';
import { createLocalSavedSearchRepository } from '../../features/assets/api/localSavedSearchRepository';
import { createSyncRepository } from '../../features/status/api/syncRepository';
import { createTagRepository } from '../../features/tags/api/tagRepository';
import { createTaskRepository } from '../../features/status/api/taskRepository';

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
