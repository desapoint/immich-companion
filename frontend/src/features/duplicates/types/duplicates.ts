export type DuplicateKeeperPolicy = 'prefer_upload' | 'prefer_external' | 'first';
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
  is_offline: boolean;
  immich_url: string | null;
  verification: 'matching' | 'mismatch' | 'unverified';
  content_checksum: string | null;
}

export interface ExactDuplicateGroup {
  duplicate_id: string;
  status: DuplicateGroupStatus;
  reason: string | null;
  keeper_asset_id: string | null;
  members: DuplicateMember[];
  eligible: boolean;
}

export interface DuplicateResult {
  generated_at: string;
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
