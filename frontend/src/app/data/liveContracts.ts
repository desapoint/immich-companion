import type { ResolvedLibraryDataSource } from './libraryContracts';
import type { SyncDataRepository, TaskRepository } from '../../features/status/types/syncContracts';

export type LiveLibraryDataSource = ResolvedLibraryDataSource & {
  readonly sync: SyncDataRepository;
  readonly tasks: TaskRepository;
};
