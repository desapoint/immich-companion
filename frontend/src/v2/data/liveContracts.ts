import type { ResolvedLibraryDataSource } from './contracts';
import type { SyncDataRepository, TaskRepository } from './syncContracts';

export type LiveLibraryDataSource = ResolvedLibraryDataSource & {
  readonly sync: SyncDataRepository;
  readonly tasks: TaskRepository;
};
