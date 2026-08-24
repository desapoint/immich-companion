export type AssetType = 'IMAGE' | 'VIDEO' | 'AUDIO' | 'OTHER';

export type SearchMode = 'simple' | 'expert';
export type SearchBooleanFilter = 'any' | 'true' | 'false';

export interface SimpleAssetSearchFilters {
  query: string;
  assetType: '' | AssetType;
  favorite: SearchBooleanFilter;
  archived: SearchBooleanFilter;
  trashed: SearchBooleanFilter;
  takenAfter: string;
  takenBefore: string;
  minWidth: string;
  maxWidth: string;
  minHeight: string;
  maxHeight: string;
  minAspectRatio: string;
  maxAspectRatio: string;
}

export interface AssetAlbumSummary {
  id: string;
  name: string;
}

export interface AssetTagSummary {
  id: string;
  name: string;
  color: string | null;
}

export interface AssetStackMember {
  id: string;
  type: string;
  original_file_name: string;
  original_mime_type: string | null;
  width: number | null;
  height: number | null;
  taken_at: string | null;
}

export interface AssetStackSummary {
  id: string;
  primary_asset_id: string;
  asset_count: number;
  assets: AssetStackMember[];
}

export interface AssetSourceSummary {
  kind: 'upload' | 'external';
  library_id: string | null;
  original_path: string | null;
}

export interface AssetCardIndicatorConfig {
  albums: boolean;
  tags: boolean;
  stack: boolean;
  external: boolean;
  immich: boolean;
}

export interface AssetSummary {
  id: string;
  type: string;
  original_file_name: string;
  original_mime_type: string | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  taken_at: string;
  file_modified_at: string;
  is_favorite: boolean;
  is_archived: boolean;
  is_trashed: boolean;
  is_offline: boolean;
  is_edited: boolean;
  visibility: string | null;
  has_metadata: boolean;
  live_photo_video_id: string | null;
  file_size_bytes: number | null;
  people_count: number;
  tag_count: number;
  stack_count: number;
  albums: AssetAlbumSummary[];
  tags: AssetTagSummary[];
  stack: AssetStackSummary | null;
  source: AssetSourceSummary;
  immich_url: string | null;
}

export interface AssetSearchResponse {
  items: AssetSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export type SearchField =
  | 'filename'
  | 'type'
  | 'taken_at'
  | 'width'
  | 'height'
  | 'aspect_ratio'
  | 'favorite'
  | 'archived'
  | 'trashed'
  | 'album';

export type SearchOperator =
  | 'contains'
  | 'equals'
  | 'not_equals'
  | 'after'
  | 'before'
  | 'at_least'
  | 'at_most'
  | 'in_album'
  | 'not_in_album';

export interface SearchCondition {
  id: string;
  kind: 'condition';
  field: SearchField;
  operator: SearchOperator;
  value: string;
}

export interface SearchGroup {
  id: string;
  kind: 'group';
  operator: 'and' | 'or';
  negate: boolean;
  children: SearchNode[];
}

export type SearchNode = SearchCondition | SearchGroup;

export interface AlbumOption {
  id: string;
  name: string;
  asset_count: number;
}

export interface AssetDetail {
  id: string;
  owner_id: string | null;
  library_id: string | null;
  type: string;
  original_file_name: string;
  original_path: string | null;
  original_mime_type: string | null;
  width: number | null;
  height: number | null;
  duration: number | null;
  taken_at: string;
  file_modified_at: string;
  created_at: string | null;
  updated_at: string | null;
  is_favorite: boolean;
  is_archived: boolean;
  is_trashed: boolean;
  is_offline: boolean;
  is_edited: boolean;
  visibility: string | null;
  live_photo_video_id: string | null;
  exif_info: Record<string, unknown> | null;
  people: Array<Record<string, unknown>>;
  tags: Array<Record<string, unknown>>;
  stack: Record<string, unknown> | null;
  immich_url: string | null;
}

export interface AssetSyncResult {
  seen: number;
  created: number;
  updated: number;
  removed: number;
  completed_at: string;
}

export type ViewerScaleMode = 'fit' | 'actual';
export type AssetComparisonSource = 'stack' | 'similar';
export type AssetComparisonActivation = 'click' | 'hover' | 'press';

export interface AssetViewerMedia {
  id: string;
  type: string;
  original_file_name: string;
  width: number | null;
  height: number | null;
  taken_at: string | null;
  file_size_bytes?: number | null;
}
