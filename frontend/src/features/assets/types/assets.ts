import type { DuplicateDisposition } from '../../../lib/types/duplicateReview';

export type AssetType = 'IMAGE' | 'VIDEO' | 'AUDIO' | 'OTHER';

export type SearchMode = 'simple' | 'expert';
export type SearchBooleanFilter = 'any' | 'true' | 'false';
export type AssetCardInlineTagMode = 'hidden' | 'matching' | 'compact';
export type AssetLayoutMode = 'normal' | 'condensed';
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
  restore_path?: string | null;
  immich_url: string | null;
}

export interface AssetSearchResponse {
  items: AssetSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  selection?: {
    id: string;
    revision: number;
    selected_count: number;
    selected_ids: string[];
  } | null;
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

export interface SavedExpertSearch {
  id: string;
  name: string;
  expression: SearchGroup;
  updated_at: string;
}

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
  last_failure: AssetSyncRunStatus | null;
  successful_watermark: string | null;
  authoritative_generation: number;
}

export type AssetSelectionMode = 'explicit' | 'all_matching';

export interface AssetSelectionRequest {
  mode: AssetSelectionMode;
  selection_id?: string | null;
  ids: string[];
  expression?: Record<string, unknown>;
  excluded_ids: string[];
}

export interface SelectionSetView {
  id: string;
  revision: number;
  selected_count: number;
  status: 'active' | 'cancelled' | 'expired';
  expires_at: string;
}

export interface SelectionSetMembershipResponse {
  selection: SelectionSetView;
  selected_ids: string[];
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
  task_id?: string | null;
}

export interface AssetTaskStatus {
  id: string;
  task_type: string;
  status: 'queued' | 'running' | 'retrying' | 'recovering' | 'cancel_requested' | 'cancelled' | 'completed' | 'failed';
  payload: Record<string, unknown>;
  checkpoint: Record<string, unknown>;
  counters: Record<string, number>;
  progress: {
    phase?: string;
    completed?: number;
    total?: number | null;
    percent?: number | null;
    detail?: string | null;
    batch?: number | null;
    batches?: number | null;
    batch_size?: number | null;
    minimum_delay_seconds?: number | null;
    assets_per_second?: number | null;
    estimated_remaining_seconds?: number | null;
    bytes_per_second?: number | null;
  };
  result: {
    summary?: {
      requested?: number;
      synced?: number;
      applied_count?: number;
      skipped_count?: number;
      failed_ids?: string[];
      missing_ids?: string[];
      errors?: Array<{ error: string; count: number }>;
      asset_id?: string;
      classification?: AssetIntegrityClassification;
      byte_size?: number;
    };
  } | null;
  error: { type?: string; message?: string } | null;
  attempt: number;
  next_attempt_at: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export type AssetIntegrityClassification = 'healthy' | 'warning' | 'malformed' | 'hash_only';
export type AssetIntegrityFreshness = 'current' | 'stale' | 'missing';

export interface AssetIntegrityReport {
  asset_id: string;
  analyzer_version: number;
  byte_size: number;
  sha1_hex: string;
  sha256_hex: string;
  detected_format: 'jpeg' | 'heic' | 'heif' | 'avif' | 'png' | 'webp' | 'gif' | 'tiff' | 'unknown';
  format_matches_declared: boolean | null;
  classification: AssetIntegrityClassification;
  structurally_valid: boolean | null;
  container_valid: boolean | null;
  decode_supported: boolean;
  decode_valid: boolean | null;
  decoded_width: number | null;
  decoded_height: number | null;
  dimensions_match_immich: boolean | null;
  jpeg_eoi_offset: number | null;
  trailing_byte_count: number;
  immich_checksum_match: boolean | null;
  issues: string[];
  analyzed_at: string;
}

export interface AssetIntegrityState {
  freshness: AssetIntegrityFreshness;
  report: AssetIntegrityReport | null;
  active_task_id: string | null;
}

export interface DuplicateReviewMember {
  id: string;
  filename: string;
  source_kind: 'upload' | 'external';
  library_id: string | null;
  verification: 'matching' | 'mismatch' | 'unverified';
  content_checksum: string | null;
  file_size_bytes: number | null;
  is_offline: boolean;
  is_stacked: boolean;
  disposition: DuplicateDisposition | null;
  recommended_disposition: DuplicateDisposition | null;
  recommendation_reason_codes: string[];
  similarity: {
    state: 'reference' | 'current' | 'pending' | 'unavailable';
    reference_asset_id: string;
    similarity_percent: number | null;
    structural_percent: number | null;
    perceptual_percent: number | null;
    color_percent: number | null;
    normalized_luminance_mae: number | null;
    normalized_luminance_rmse: number | null;
    normalized_luminance_ssim: number | null;
    aspect_ratio_difference: number | null;
    dimensions_equal: boolean | null;
    exact_thumbnail_match: boolean | null;
    exact_pixel_match: boolean | null;
    model_version: string | null;
    feature_version: number | null;
    comparison_version: number | null;
  } | null;
  preservation: {
    pixel_normalization_version: number;
    pixel_sha256: string;
    decoded_width: number;
    decoded_height: number;
    bit_depth: number;
    channel_count: number;
    has_alpha: boolean;
    color_space: string;
    orientation: number | null;
    icc_profile_present: boolean;
    has_exif: boolean;
    has_capture_time: boolean;
    has_camera_info: boolean;
    has_gps: boolean;
    has_orientation_metadata: boolean;
    metadata_richness: number;
  } | null;
}

export interface DuplicateReviewContext {
  group_id: string;
  discovery_source: 'immich_duplicate' | 'companion_similarity';
  discovery_metadata: Record<string, string>;
  classification: 'exact_file' | 'exact_pixels' | 'likely_same' | 'similar' | 'mismatch' | 'unverified' | 'unavailable' | 'ineligible';
  status: 'exact' | 'unverified' | 'mismatch' | 'ineligible';
  reason: string | null;
  eligible: boolean;
  keeper_policy: 'most_recent' | 'prefer_upload' | 'prefer_external' | 'first';
  recommended_keeper_asset_id: string | null;
  selected_keeper_asset_id: string | null;
  selected_action: 'automatic' | 'resolve' | 'keep_all' | 'delete_all' | 'stack_all' | 'mixed' | 'none';
  stack_primary_asset_id: string | null;
  recommendation_reason_codes: string[];
  members: DuplicateReviewMember[];
  current_integrity: AssetIntegrityState | null;
  similarity_loading: boolean;
  similarity_error: string | null;
}

export interface AssetIntegrityAnalyzeResponse {
  state: 'ready' | 'pending';
  freshness: AssetIntegrityFreshness;
  report: AssetIntegrityReport | null;
  task_id: string | null;
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
  | 'set_stack_primary'
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
  | 'set_stack_primary'
  | 'remove_from_stack'
  | 'remove_stack';

export type StackResolution = 'keep_existing' | 'move_selected' | 'include_existing';

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
  stack_conflicts: StackConflict[];
  stack_primary_asset_id: string | null;
}

export interface StackConflict {
  stack_id: string;
  selected_count: number;
  member_count: number;
  includes_unselected: boolean;
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

export interface AssetActionTaskStart {
  task_id: string;
}

export interface AssetActionRelationResult {
  relation_id: string;
  applied_ids: string[];
  skipped_ids: string[];
  failed_ids: string[];
}

export type ViewerScaleMode = 'fit' | 'actual';
export type AssetComparisonSource = 'stack' | 'similar' | 'duplicate';
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
