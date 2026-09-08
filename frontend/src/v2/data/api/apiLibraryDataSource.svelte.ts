import {
  cancelTask,
  getAssetSyncStatus,
  openTaskUpdates,
  startAssetSync,
} from '../../../features/assets/api/assetApi';
import {
  loadSyncRuntimeSettings,
  loadSyncSchedules,
  saveSyncRuntimeSettings,
  saveSyncSchedule,
} from '../../../features/settings/api/settingsApi';
import type {
  DuplicateRepository,
} from '../contracts';
import type { LiveLibraryDataSource, SyncDataRepository } from '../liveContracts';
import { notImplemented } from '../notImplemented';
import { createAlbumRepository } from './albumRepository';
import { createAssetApiProfile } from './assetRepository';
import { createLocalSavedSearchRepository } from './localSavedSearchRepository';
import { createTagRepository } from './tagRepository';

function unsupportedRepository<T extends object>(area: string): T {
  return new Proxy({}, {
    get(_target, property) {
      if (property === 'then') return undefined;
      return () => notImplemented(`${area}.${String(property)}`);
    },
  }) as T;
}

const sync: SyncDataRepository = {
  status: (signal) => getAssetSyncStatus(signal),
  start: (mode) => startAssetSync(mode),
  cancel: (taskId) => cancelTask(taskId),
  runtimeSettings: () => loadSyncRuntimeSettings(),
  saveRuntimeSettings: (value) => saveSyncRuntimeSettings(value),
  schedules: () => loadSyncSchedules(),
  saveSchedule: (name, value) => saveSyncSchedule(name, value),
  openUpdates: (onstatus, onerror, onclose) => openTaskUpdates(onstatus, onerror, onclose),
};

/**
 * Production V2 data source.
 *
 * Only explicitly connected feature repositories are implemented here.
 * Every other repository is present at the contract boundary but fails closed with the
 * standard V2NotImplementedError. A backend endpoint existing is therefore not enough
 * to make a V2 action live; the operation must be explicitly implemented here.
 */
export function createApiLibraryDataSource(): LiveLibraryDataSource {
  const assetProfile = createAssetApiProfile();
  return {
    kind: 'api',
    initialize: async () => undefined,
    assets: assetProfile.assets,
    albums: createAlbumRepository(),
    tags: createTagRepository(),
    savedSearches: createLocalSavedSearchRepository(),
    duplicates: unsupportedRepository<DuplicateRepository>('duplicates'),
    media: assetProfile.media,
    navigation: assetProfile.navigation,
    sync,
  };
}
