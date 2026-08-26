export type AssetType = 'IMAGE' | 'VIDEO' | 'AUDIO' | 'OTHER';

export type SearchMode = 'simple' | 'expert';
export type SearchBooleanFilter = 'any' | 'true' | 'false';
export type AssetCardInlineTagMode = 'hidden' | 'matching' | 'compact';
export type AssetSortField =
  | 'taken_at'
  | 'filename'
  | 'created_at'
  | 'modified_at'
  | 'width'
  | 'height';
export type AssetSortDirection = 'asc' | 'desc';

export interface AssetSort {
  field: AssetSortField;
  direction: AssetSortDirection;
}

export interface SimpleAssetSearchFilters {
  query: string;
  assetType: '' | AssetType;
  favorite: SearchBooleanFilter;
  archived: SearchBooleanFilter;
  trashed: SearchBooleanFilter;
  albumIds: string[];
  tagIds: string[];
  noAlbum: boolean;
  noTag: boolean;
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
  inlineTags: AssetCardInlineTagMode;
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
  | 'album'
  | 'tag';

export type SearchOperator =
  | 'contains'
  | 'equals'
  | 'not_equals'
  | 'after'
  | 'before'
  | 'at_least'
  | 'at_most'
  | 'in_any'
  | 'in_all'
  | 'not_in_any'
  | 'has_none';

export interface SearchCondition {
  id: string;
  kind: 'condition';
  field: SearchField;
  operator: SearchOperator;
  value: string | string[];
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

export interface TagOption {
  id: string;
  name: string;
  color: string | null;
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

export type AssetSyncMode = 'incremental' | 'full';
export type AssetSyncRunState = 'queued' | 'running' | 'completed' | 'failed' | 'recovering' | 'retrying';

export interface AssetSyncRunStatus {
  id: string;
  task_id?: string | null;
  mode: AssetSyncMode;
  status: AssetSyncRunState;
  phase: string;
  generation: number;
  window_start: string | null;
  window_end: string;
  cursor: string | null;
  counters: Record<string, number>;
  attempts: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  heartbeat_at: string | null;
  completed_at: string | null;
  progress: AssetSyncProgress;
}

export interface AssetSyncProgress {
  phase: string;
  completed: number;
  total: number | null;
  percent: number | null;
  detail: string | null;
}

export interface AssetSyncCoordinatorStatus {
  active: AssetSyncRunStatus | null;
  pending: AssetSyncRunStatus | null;
  last_success: AssetSyncRunStatus | null;
  successful_watermark: string | null;
  authoritative_generation: number;
}

export type AssetSelectionMode = 'explicit' | 'all_matching';

export interface AssetSelectionRequest {
  mode: AssetSelectionMode;
  ids: string[];
  expression?: Record<string, unknown>;
  excluded_ids: string[];
}

export interface AssetSelectionSummary {
  total: number;
  archived: number;
  unarchived: number;
  favorite: number;
  not_favorite: number;
  trashed: number;
  not_trashed: number;
  archive_action: 'archive' | 'unarchive' | null;
  favorite_action: 'favorite' | 'unfavorite' | null;
  can_trash: boolean;
  can_restore: boolean;
}

export interface AssetSelectionResolution {
  ids: string[];
  missing_ids: string[];
  summary: AssetSelectionSummary;
}

export interface AssetSelectionSyncResult {
  requested: number;
  synced: number;
}

export type AssetActionIntent =
  | 'archive_toggle'
  | 'favorite_toggle'
  | 'trash'
  | 'restore'
  | 'add_album'
  | 'add_tag'
  | 'remove_album'
  | 'remove_tag'
  | 'stack'
  | 'remove_from_stack'
  | 'remove_stack';

export type AssetActionOperation =
  | 'archive'
  | 'unarchive'
  | 'favorite'
  | 'unfavorite'
  | 'trash'
  | 'restore'
  | 'add_album'
  | 'add_tag'
  | 'remove_album'
  | 'remove_tag'
  | 'stack'
  | 'remove_from_stack'
  | 'remove_stack';

export interface AssetActionPlan {
  id: string;
  action: AssetActionIntent;
  operation: AssetActionOperation;
  relation_ids: string[];
  relations: AssetActionRelationPlan[];
  target_count: number;
  applicable_count: number;
  skipped_count: number;
  missing_ids: string[];
  destructive: boolean;
  status: 'planned' | 'running' | 'completed' | 'failed' | 'drifted' | 'expired';
  expires_at: string;
}

export interface AssetActionRelationPlan {
  relation_id: string;
  applicable_count: number;
  skipped_count: number;
}

export interface AssetActionResult {
  plan_id: string;
  operation: AssetActionOperation;
  target_count: number;
  applied_count: number;
  skipped_count: number;
  applied_ids: string[];
  skipped_ids: string[];
  failed_ids: string[];
  relation_results: AssetActionRelationResult[];
  verified: boolean;
  status: 'planned' | 'running' | 'completed' | 'failed' | 'drifted' | 'expired';
}

export interface AssetActionRelationResult {
  relation_id: string;
  applied_ids: string[];
  skipped_ids: string[];
  failed_ids: string[];
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
