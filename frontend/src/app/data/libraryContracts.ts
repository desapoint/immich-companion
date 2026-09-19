import type {
  AlbumRepository,
  AssetRepository,
  LegacyMediaRepository,
  MediaRepository,
  SavedSearchRepository,
  TagRepository,
  ViewerNavigationRepository,
} from '../../lib/types/libraryContracts';
import type { DuplicateRepository } from '../../features/duplicates/types/contracts';

export interface LibraryDataSource {
  readonly kind: 'demo' | 'api';
  readonly assets: AssetRepository;
  readonly albums: AlbumRepository;
  readonly tags: TagRepository;
  readonly savedSearches?: SavedSearchRepository;
  readonly duplicates: DuplicateRepository;
  readonly media: MediaRepository | LegacyMediaRepository;
  initialize(): Promise<void>;
}

export type ResolvedLibraryDataSource = Omit<LibraryDataSource, 'media' | 'savedSearches'> & {
  readonly media: MediaRepository;
  readonly navigation: ViewerNavigationRepository;
  readonly savedSearches: SavedSearchRepository;
};
