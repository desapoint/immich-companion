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
  AlbumRepository,
  AssetRepository,
  DuplicateRepository,
  MediaRepository,
  SavedSearchRepository,
  TagRepository,
  ViewerNavigationRepository,
} from '../contracts';
import type { LiveLibraryDataSource, SyncDataRepository } from '../liveContracts';
import { notImplemented } from '../notImplemented';

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
 * Only synchronization and its configuration are intentionally implemented right now.
 * Every other repository is present at the contract boundary but fails closed with the
 * standard V2NotImplementedError. A backend endpoint existing is therefore not enough
 * to make a V2 action live; the operation must be explicitly implemented here.
 */
export function createApiLibraryDataSource(): LiveLibraryDataSource {
  return {
    kind: 'api',
    initialize: async () => undefined,
    assets: unsupportedRepository<AssetRepository>('assets'),
    albums: unsupportedRepository<AlbumRepository>('albums'),
    tags: unsupportedRepository<TagRepository>('tags'),
    savedSearches: unsupportedRepository<SavedSearchRepository>('savedSearches'),
    duplicates: unsupportedRepository<DuplicateRepository>('duplicates'),
    media: unsupportedRepository<MediaRepository>('media'),
    navigation: unsupportedRepository<ViewerNavigationRepository>('navigation'),
    sync,
  };
}
