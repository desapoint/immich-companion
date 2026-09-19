import type { ResolvedLibraryDataSource } from '../../v2/data/contracts';
import type { SyncDataRepository, TaskRepository } from '../../features/status/types/syncContracts';

export type LiveLibraryDataSource = ResolvedLibraryDataSource & {
  readonly sync: SyncDataRepository;
  readonly tasks: TaskRepository;
};
