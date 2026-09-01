import type { DuplicateKeeperPolicy, ExactFilePolicyAction } from '../../../lib/types/duplicatePolicy';
import type { DuplicateDecisionSource, DuplicateDecisionStatus, DuplicateDisposition } from '../../../lib/types/duplicateReview';

export type { DuplicateKeeperPolicy } from '../../../lib/types/duplicatePolicy';
export type DuplicateGroupStatus = 'exact' | 'unverified' | 'mismatch' | 'ineligible';
export type DuplicatePlanAction = 'resolve' | 'keep_all' | 'delete_all' | 'stack_all' | 'none';
export type DuplicateActionSelection = DuplicatePlanAction | 'automatic';
export type { DuplicateDisposition } from '../../../lib/types/duplicateReview';

export interface DuplicateAnalysisOptions {
  keeper_policy: DuplicateKeeperPolicy;
  external_library_ids: string[];
  verify_upload_streams: boolean;
  automatic_handling_enabled: boolean;
  preselect_safe_groups: boolean;
  exact_file_action: ExactFilePolicyAction;
  analyze_automatically: boolean;
}

export interface DuplicateMember {
  id: string;
  source_kind: 'upload' | 'external';
  library_id: string | null;
  original_file_name: string;
  original_mime_type: string | null;
  file_size_bytes: number | null;
  file_modified_at: string;
  uploaded_at: string | null;
  is_offline: boolean;
  is_stacked: boolean;
  immich_url: string | null;
  verification: 'matching' | 'mismatch' | 'unverified';
  content_checksum: string | null;
  evidence: {
    analysis_freshness: 'current' | 'stale' | 'missing';
    integrity_status: 'healthy' | 'warning' | 'malformed' | 'hash_only' | null;
    issue_codes: string[];
    detected_format: 'jpeg' | 'heic' | 'heif' | 'avif' | 'png' | 'webp' | 'gif' | 'tiff' | 'unknown' | null;
    format_matches_declared: boolean | null;
    decode_supported: boolean | null;
    decode_valid: boolean | null;
    decoded_width: number | null;
    decoded_height: number | null;
    dimensions_match_immich: boolean | null;
  };
  similarity: DuplicateSimilarityEvidence | null;
  preservation: DuplicatePreservationEvidence | null;
  recommended_disposition?: DuplicateDisposition | null;
  recommendation_reason_codes?: string[];
}

export interface DuplicateSimilarityEvidence {
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
}

export interface DuplicatePreservationEvidence {
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
}

export interface ExactDuplicateGroup {
  group_id: string;
  discovery_source: 'immich_duplicate' | 'companion_similarity';
  provider_group_id: string | null;
  discovery_metadata?: Record<string, string>;
  classification: 'exact_file' | 'exact_pixels' | 'likely_same' | 'similar' | 'mismatch' | 'unverified' | 'unavailable' | 'ineligible';
  status: DuplicateGroupStatus;
  reason: string | null;
  keeper_asset_id: string | null;
  recommended_action: 'resolve' | 'keep_all' | 'delete_all' | 'stack_all' | 'none';
  recommended_primary_asset_id: string | null;
  recommendation_reason_codes: string[];
  auto_resolvable: boolean;
  auto_selected: boolean;
  action_source: 'automatic' | 'manual' | 'none';
  primary_source: 'automatic' | 'manual' | 'none';
  manual_action: DuplicatePlanAction | null;
  manual_primary_asset_id: string | null;
  effective_action: DuplicatePlanAction;
  effective_primary_asset_id: string | null;
  review_status: 'pending' | 'manually_configured' | 'reviewed_keep_all' | 'reviewed_resolve' | 'reviewed_delete_all' | 'reviewed_stack_all' | 'review_later' | 'drifted';
  member_fingerprint: string;
  members: DuplicateMember[];
  eligible: boolean;
}

export interface DuplicatePreviewRequest {
  group_id: string;
  discovery_source: 'immich_duplicate' | 'companion_similarity';
  discovery_metadata: Record<string, string>;
  classification: ExactDuplicateGroup['classification'];
  status: DuplicateGroupStatus;
  reason: string | null;
  eligible: boolean;
  keeper_policy: DuplicateKeeperPolicy;
  recommended_keeper_asset_id: string | null;
  selected_keeper_asset_id: string | null;
  selected_action: DuplicateActionSelection;
  member_decisions: Record<string, DuplicateDisposition>;
  stack_primary_asset_id: string | null;
  recommendation_reason_codes: string[];
  members: DuplicateMember[];
  initial_index: number;
  onmemberdispositionchange?: (assetId: string, disposition: DuplicateDisposition) => void;
  onstackprimarychange?: (assetId: string) => void;
  onsimilarityreferencechange?: (assetId: string) => Promise<DuplicateMember[]>;
  onpreviousgroup?: () => void;
  onnextgroup?: () => void;
}

export interface DuplicateMemberDraftDecision {
  asset_id: string;
  disposition: DuplicateDisposition;
  source: DuplicateDecisionSource;
  status: DuplicateDecisionStatus;
}

export interface DuplicateGroupDraft {
  group_id: string;
  discovery_source: ExactDuplicateGroup['discovery_source'];
  member_fingerprint: string;
  decisions: DuplicateMemberDraftDecision[];
  stack_primary_asset_id: string | null;
  metadata_keeper_asset_id: string | null;
  status: 'pending' | 'completed';
  stale: boolean;
}

export interface DuplicateWorkspaceGroupReference {
  group_id: string;
  discovery_source: ExactDuplicateGroup['discovery_source'];
  member_fingerprint: string;
}

export interface DuplicateWorkspaceState {
  initialized: boolean;
  selected_group_ids: string[];
  active_group_id: string | null;
  stale_selected_groups: DuplicateWorkspaceGroupReference[];
  drafts: DuplicateGroupDraft[];
}

export interface DuplicateResult {
  generated_at: string;
  analysis_task_id: string | null;
  analysis_pending_count: number;
  analysis_candidate_count: number;
  analysis_cached_count: number;
  group_count: number;
  exact_group_count: number;
  unverified_group_count: number;
  mismatch_group_count: number;
  ineligible_group_count: number;
  groups: ExactDuplicateGroup[];
}

export interface DuplicateTaskStatus {
  id: string;
  task_type: string;
  status: 'queued' | 'running' | 'retrying' | 'recovering' | 'cancel_requested' | 'cancelled' | 'completed' | 'failed';
  progress: {
    percent?: number | null;
    detail?: string | null;
    completed?: number;
    total?: number | null;
  };
  error: { message?: string } | null;
  result: { summary?: Record<string, unknown> } | null;
}

export interface SimilarityScanSummary {
  scan_id: string;
  similarity_threshold: number;
  scope: 'all_eligible_assets';
  model_version: string;
  feature_version: number;
  comparison_version: number;
  asset_count: number;
  candidate_count: number;
  match_count: number;
  completed_at: string;
}

export interface DuplicateResolutionPlan {
  id: string;
  status: 'planned' | 'running' | 'completed' | 'failed' | 'drifted' | 'expired';
  groups: Array<{
    group_id: string;
    discovery_source: 'immich_duplicate' | 'companion_similarity';
    provider_group_id: string | null;
    action: Exclude<DuplicatePlanAction, 'none'>;
    keeper_asset_id: string | null;
    member_asset_ids: string[];
    keep_asset_ids: string[];
    trash_asset_ids: string[];
    follow_up: {
      type: 'stack';
      primary_asset_id: string;
      member_asset_ids: string[];
    } | null;
    execution_state: 'pending' | 'duplicate_resolved' | 'follow_up_pending' | 'completed' | 'failed' | 'drifted';
    member_fingerprint: string;
    members: Array<{ asset_id: string; disposition: 'keep' | 'delete' | 'stack' | 'no_change'; primary: boolean }>;
  }>;
  group_count: number;
  resolve_group_count: number;
  keep_all_group_count: number;
  delete_all_group_count: number;
  stack_group_count: number;
  trash_asset_count: number;
  retained_asset_count: number;
  zero_survivor_group_count: number;
  expires_at: string;
  destructive: boolean;
}
