export type DuplicateKeeperPolicy = 'most_recent' | 'prefer_upload' | 'prefer_external' | 'first';
export type DuplicateGroupStatus = 'exact' | 'unverified' | 'mismatch' | 'ineligible';

export interface DuplicateAnalysisOptions {
  keeper_policy: DuplicateKeeperPolicy;
  external_library_ids: string[];
  verify_upload_streams: boolean;
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
}

export interface ExactDuplicateGroup {
  duplicate_id: string;
  group_id: string;
  discovery_source: 'immich_duplicate' | 'companion_similarity';
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
  members: DuplicateMember[];
  eligible: boolean;
}

export interface DuplicatePreviewRequest {
  duplicate_id: string;
  status: DuplicateGroupStatus;
  reason: string | null;
  eligible: boolean;
  keeper_policy: DuplicateKeeperPolicy;
  recommended_keeper_asset_id: string | null;
  selected_keeper_asset_id: string | null;
  recommendation_reason_codes: string[];
  members: DuplicateMember[];
  initial_index: number;
}

export interface DuplicateResult {
  generated_at: string;
  analysis_task_id: string | null;
  analysis_pending_count: number;
  group_count: number;
  exact_group_count: number;
  unverified_group_count: number;
  mismatch_group_count: number;
  ineligible_group_count: number;
  groups: ExactDuplicateGroup[];
}

export interface DuplicateTaskStatus {
  id: string;
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

export interface DuplicateResolutionPlan {
  id: string;
  status: 'planned' | 'running' | 'completed' | 'failed' | 'drifted' | 'expired';
  groups: Array<{
    duplicate_id: string;
    keeper_asset_id: string;
    trash_asset_ids: string[];
  }>;
  group_count: number;
  trash_asset_count: number;
  expires_at: string;
  destructive: boolean;
}
