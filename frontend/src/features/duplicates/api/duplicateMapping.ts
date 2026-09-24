import type { AssetRecord, DuplicateDecision, DuplicateGroupRecord, DuplicateResolutionPlan, DuplicateState } from '../types/contracts';
import { referenceFirstDuplicateMembers } from '../utils/duplicatePresentation';
import { parseStackResolution } from '../types/stackResolution';
import type { ApiDuplicateDraft, ApiDuplicateGroup, ApiDuplicateMember } from './duplicateRepository';

function similarity(member: ApiDuplicateMember): number | null {
  if (!member.similarity) return null;
  return member.similarity.state === 'reference' ? 100 : member.similarity.similarity_percent;
}

function similarityEvidence(member: ApiDuplicateMember) {
  if (!member.similarity) return null;
  return {
    structuralPercent: member.similarity.structural_percent,
    perceptualPercent: member.similarity.perceptual_percent,
    colorPercent: member.similarity.color_percent,
    ...(member.similarity.normalized_luminance_mae !== undefined ? { normalizedLuminanceMae: member.similarity.normalized_luminance_mae } : {}),
    ...(member.similarity.normalized_luminance_rmse !== undefined ? { normalizedLuminanceRmse: member.similarity.normalized_luminance_rmse } : {}),
    ...(member.similarity.normalized_luminance_ssim !== undefined ? { normalizedLuminanceSsim: member.similarity.normalized_luminance_ssim } : {}),
    ...(member.similarity.aspect_ratio_difference !== undefined ? { aspectRatioDifference: member.similarity.aspect_ratio_difference } : {}),
    ...(member.similarity.dimensions_equal !== undefined ? { dimensionsEqual: member.similarity.dimensions_equal } : {}),
    ...(member.similarity.exact_thumbnail_match !== undefined ? { exactThumbnailMatch: member.similarity.exact_thumbnail_match } : {}),
    ...(member.similarity.exact_pixel_match !== undefined ? { exactPixelMatch: member.similarity.exact_pixel_match } : {}),
    ...(member.similarity.detail_changed_percent !== undefined ? { detailChangedPercent: member.similarity.detail_changed_percent } : {}),
    ...(member.similarity.detail_source !== undefined ? { detailSource: member.similarity.detail_source } : {}),
    ...(member.similarity.validated_width !== undefined ? { validatedWidth: member.similarity.validated_width } : {}),
    ...(member.similarity.validated_height !== undefined ? { validatedHeight: member.similarity.validated_height } : {}),
    ...(member.similarity.reference_validated_width !== undefined ? { referenceValidatedWidth: member.similarity.reference_validated_width } : {}),
    ...(member.similarity.reference_validated_height !== undefined ? { referenceValidatedHeight: member.similarity.reference_validated_height } : {}),
    ...(member.similarity.model_version !== undefined ? { modelVersion: member.similarity.model_version } : {}),
    ...(member.similarity.feature_version !== undefined ? { featureVersion: member.similarity.feature_version } : {}),
    ...(member.similarity.comparison_version !== undefined ? { comparisonVersion: member.similarity.comparison_version } : {}),
  };
}

function admissionEvidence(member: ApiDuplicateMember) {
  if (!member.admission) return null;
  return {
    admittedByAssetId: member.admission.admitted_by_asset_id,
    admissionSimilarityPercent: member.admission.admission_similarity_percent,
    bestGroupMatchAssetId: member.admission.best_group_match_asset_id,
    bestGroupMatchSimilarityPercent: member.admission.best_group_match_similarity_percent,
    linkDepth: member.admission.link_depth,
    modelVersion: member.admission.model_version,
    featureVersion: member.admission.feature_version,
    comparisonVersion: member.admission.comparison_version,
    configFingerprint: member.admission.config_fingerprint,
  };
}

function preservationEvidence(member: ApiDuplicateMember) {
  if (!member.preservation) return null;
  return {
    origin: member.preservation.origin,
    pixelNormalizationVersion: member.preservation.pixel_normalization_version,
    pixelSha256: member.preservation.pixel_sha256,
    decodedWidth: member.preservation.decoded_width,
    decodedHeight: member.preservation.decoded_height,
    bitDepth: member.preservation.bit_depth,
    channelCount: member.preservation.channel_count,
    hasAlpha: member.preservation.has_alpha,
    colorSpace: member.preservation.color_space,
    orientation: member.preservation.orientation,
    iccProfilePresent: member.preservation.icc_profile_present,
    hasExif: member.preservation.has_exif,
    hasCaptureTime: member.preservation.has_capture_time,
    hasCameraInfo: member.preservation.has_camera_info,
    hasGps: member.preservation.has_gps,
    hasOrientationMetadata: member.preservation.has_orientation_metadata,
    metadataRichness: member.preservation.metadata_richness,
  };
}

function assetType(mimeType: string | null): AssetRecord['asset_type'] {
  if (mimeType?.startsWith('video/')) return 'VIDEO';
  if (mimeType?.startsWith('audio/')) return 'AUDIO';
  if (mimeType?.startsWith('image/')) return 'IMAGE';
  return 'OTHER';
}

function assetFromMember(member: ApiDuplicateMember): AssetRecord {
  return {
    id: member.id, owner_id: null, library_id: member.library_id, asset_type: assetType(member.original_mime_type),
    original_file_name: member.original_file_name, original_path: null, original_mime_type: member.original_mime_type,
    checksum: null, file_size_bytes: member.file_size_bytes, width: member.evidence.decoded_width ?? null,
    height: member.evidence.decoded_height ?? null, duration: null, file_created_at: member.uploaded_at ?? member.file_modified_at,
    file_modified_at: member.file_modified_at, local_date_time: null, immich_created_at: member.uploaded_at,
    immich_updated_at: null, is_favorite: false, is_archived: false, is_offline: member.is_offline, is_edited: false,
    has_metadata: false, visibility: null, live_photo_video_id: null, tags: [], albums: [], stack: null, synced_at: member.file_modified_at,
  };
}

function savedDecisions(draft: ApiDuplicateDraft | undefined): Record<string, DuplicateDecision> {
  return Object.fromEntries((draft?.decisions ?? []).map((decision) => [decision.asset_id, decision.disposition])) as Record<string, DuplicateDecision>;
}

function groupState(group: ApiDuplicateGroup, draft: ApiDuplicateDraft | undefined): DuplicateState {
  if (!group.eligible || group.status === 'ineligible' || draft?.stale) return 'Blocked';
  const decisionCount = draft?.decisions.length ?? 0;
  if (decisionCount > 0 && decisionCount < group.members.length) return 'Needs decisions';
  if (decisionCount === group.members.length || group.auto_resolvable || group.auto_selected) return 'Actionable';
  return 'Needs review';
}

export function mapDuplicateGroup(
  group: ApiDuplicateGroup,
  draft: ApiDuplicateDraft | undefined,
  selected: boolean,
): DuplicateGroupRecord {
  return {
    id: group.group_id,
    discoverySources: group.discovery_sources?.length ? group.discovery_sources : [group.discovery_source],
    state: groupState(group, draft), autoReady: group.auto_selected, kind: group.classification.replaceAll('_', ' '),
    reason: group.reason, referenceAssetId: group.reference_asset_id ?? null, groupSimilarity: group.group_similarity_percent ?? null,
    similarityEngine: group.similarity_engine ?? null, similarityModelVersion: group.similarity_model_version ?? null,
    similarityFeatureVersion: group.similarity_feature_version ?? null, similarityComparisonVersion: group.similarity_comparison_version ?? null,
    similarityValidationMode: group.similarity_validation_mode ?? null, similarityThresholdPercent: group.similarity_threshold_percent ?? null,
    memberFingerprint: group.member_fingerprint, selected, savedDecisions: savedDecisions(draft),
    stackPrimaryAssetId: draft?.stack_primary_asset_id ?? null, stackResolution: parseStackResolution(draft?.stack_resolution ?? 'move_selected'),
    members: referenceFirstDuplicateMembers(group.members.map((member) => ({
      asset: assetFromMember(member), similarity: similarity(member), similarityEvidence: similarityEvidence(member),
      admission: admissionEvidence(member), preservation: preservationEvidence(member),
    })), group.reference_asset_id),
  };
}

export function actionFor(decisions: Record<string, DuplicateDecision>): 'resolve' | 'keep_all' | 'stack_all' | 'mixed' {
  const values = Object.values(decisions);
  if (values.every((decision) => decision === 'keep')) return 'keep_all';
  if (values.every((decision) => decision === 'stack')) return 'stack_all';
  if (values.includes('stack')) return 'mixed';
  return 'resolve';
}

export function primaryFor(resolution: DuplicateResolutionPlan, memberIds: readonly string[]): string | null {
  const stack = resolution.stacks.find((candidate) => candidate.assetIds.some((id) => memberIds.includes(id)));
  if (stack?.primaryAssetId && resolution.decisions[stack.primaryAssetId] === 'stack') return stack.primaryAssetId;
  return memberIds.find((id) => resolution.decisions[id] === 'stack')
    ?? memberIds.find((id) => resolution.decisions[id] === 'keep')
    ?? null;
}

export function groupResolution(resolution: DuplicateResolutionPlan, group: ApiDuplicateGroup): DuplicateResolutionPlan {
  const ids = new Set(group.members.map((member) => member.id));
  return {
    decisions: Object.fromEntries(Object.entries(resolution.decisions).filter(([id]) => ids.has(id))),
    stacks: resolution.stacks.filter((stack) => stack.groupId === group.group_id),
  };
}
