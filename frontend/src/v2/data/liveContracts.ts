import type {
  AssetSyncCoordinatorStatus,
  AssetSyncMode,
  AssetSyncRunStatus,
  AssetTaskStatus,
} from '../../features/assets/types/assets';
import type { SyncRuntimeSettings, SyncSchedule } from '../../features/settings/types/settings';
import type { ResolvedLibraryDataSource } from './contracts';

export interface SyncDataRepository {
  status(signal?: AbortSignal): Promise<AssetSyncCoordinatorStatus>;
  start(mode: AssetSyncMode): Promise<AssetSyncRunStatus>;
  cancel(taskId: string): Promise<AssetTaskStatus>;
  runtimeSettings(): Promise<SyncRuntimeSettings>;
  saveRuntimeSettings(value: SyncRuntimeSettings): Promise<SyncRuntimeSettings>;
  schedules(): Promise<SyncSchedule[]>;
  saveSchedule(
    name: string,
    value: Pick<SyncSchedule, 'enabled' | 'cron_expression'>,
  ): Promise<SyncSchedule>;
  openUpdates(
    onstatus: (task: AssetTaskStatus) => void,
    onerror?: () => void,
    onclose?: () => void,
  ): WebSocket;
}

export type LiveLibraryDataSource = ResolvedLibraryDataSource & {
  readonly sync: SyncDataRepository;
};
