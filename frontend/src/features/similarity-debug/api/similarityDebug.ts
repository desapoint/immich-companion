import { jsonRequest, requestJson } from '../../../lib/api/http';

export type SimilarityDebugEvidenceState = 'current' | 'unavailable' | 'missing_or_stale';
export type SimilarityDebugValidationMode = 'reference' | 'linked' | 'strict';

export type SimilarityDebugRequest = {
  asset_ids: string[];
  similarity_threshold: number;
  validation_mode: SimilarityDebugValidationMode;
  max_link_depth: number;
  anchor_asset_id: string | null;
  maximum_perceptual_distance: number;
  maximum_aspect_difference: number;
};

export type SimilarityDebugAsset = {
  asset_id: string;
  evidence_state: SimilarityDebugEvidenceState;
  reason: string | null;
  width: number | null;
  height: number | null;
  fingerprint_origin: string | null;
  model_version: string | null;
  feature_version: number | null;
  config_fingerprint: string | null;
};

export type SimilarityDebugLocalDiagnostics = {
  changed_percent: number;
  localized_changed_percent: number;
  coherent_changed_percent: number;
  largest_changed_region_percent: number;
  substantial_region_count: number;
  aligned_changed_percent: number;
  raw_similarity_percent: number;
  aligned_similarity_percent: number;
  alignment_applied: boolean;
  alignment_shift_percent: number;
  alignment_overlap_percent: number;
  rows: number;
  columns: number;
  cells: number[][];
  source: 'original' | 'transcoded' | 'preview';
};

export type SimilarityDebugPair = {
  asset_id_left: string;
  asset_id_right: string;
  evidence_available: boolean;
  perceptual_distance: number | null;
  maximum_perceptual_distance: number;
  perceptual_gate_pass: boolean;
  aspect_ratio_difference: number | null;
  maximum_aspect_difference: number;
  aspect_gate_pass: boolean;
  candidate_pair_pass: boolean;
  neighbor_allocation_simulated: boolean;
  similarity_percent: number | null;
  structural_percent: number | null;
  perceptual_percent: number | null;
  color_percent: number | null;
  normalized_luminance_mae: number | null;
  normalized_luminance_rmse: number | null;
  normalized_luminance_ssim: number | null;
  dimensions_equal: boolean | null;
  exact_thumbnail_match: boolean | null;
  detail_changed_percent: number | null;
  detail_source: 'original' | 'transcoded' | 'preview' | null;
  similarity_threshold: number;
  similarity_threshold_pass: boolean;
  would_pass_pair_pipeline: boolean;
  exclusion_reason: string | null;
  local_diagnostics: SimilarityDebugLocalDiagnostics | null;
  model_version: string | null;
  feature_version: number | null;
  comparison_version: number | null;
};

export type SimilarityDebugAdmission = {
  asset_id: string;
  admitted_by_asset_id: string | null;
  admission_similarity_percent: number | null;
  best_group_match_asset_id: string | null;
  best_group_match_similarity_percent: number | null;
  link_depth: number;
};

export type SimilarityDebugGroup = {
  asset_ids: string[];
  anchor_asset_id: string;
  validation_mode: SimilarityDebugValidationMode;
  minimum_similarity_percent: number;
  maximum_similarity_percent: number;
  pair_count: number;
  admission_evidence: SimilarityDebugAdmission[];
};

export type SimilarityDebugResponse = {
  assets: SimilarityDebugAsset[];
  pairs: SimilarityDebugPair[];
  groups: SimilarityDebugGroup[];
  neighbor_allocation_simulated: boolean;
  note: string;
};

export function runSimilarityDebug(request: SimilarityDebugRequest, signal?: AbortSignal): Promise<SimilarityDebugResponse> {
  return requestJson<SimilarityDebugResponse>(
    '/api/v2/similarity-debug/compare',
    { ...jsonRequest('POST', request), signal },
  );
}
