<script lang="ts">
  import { onMount } from 'svelte';

  import { getAssetDetail, getAssetIntegrity } from '../api/assetApi';
  import type { DuplicateDisposition } from '../../../lib/types/duplicateReview';
  import { resolveStackPrimary } from '../../../lib/utils/duplicateReview';
  import type { AssetDetail, AssetIntegrityState, AssetSummary, DuplicateReviewContext } from '../types/assets';
  import AssetViewerDialog from './AssetViewerDialog.svelte';

  export interface DuplicatePreviewMember {
    id: string;
    source_kind: 'upload' | 'external';
    library_id: string | null;
    original_file_name: string;
    original_mime_type: string | null;
    file_size_bytes: number | null;
    file_modified_at: string;
    is_offline: boolean;
    is_stacked: boolean;
    immich_url: string | null;
    similarity: DuplicateReviewContext['members'][number]['similarity'];
    preservation: DuplicateReviewContext['members'][number]['preservation'];
    recommended_disposition?: DuplicateDisposition | null;
    recommendation_reason_codes?: string[];
  }

  interface DuplicatePreviewReview {
    group_id: string;
    discovery_source: 'immich_duplicate' | 'companion_similarity';
    discovery_metadata: Record<string, string>;
    classification: DuplicateReviewContext['classification'];
    status: 'exact' | 'unverified' | 'mismatch' | 'ineligible';
    reason: string | null;
    eligible: boolean;
    keeper_policy: 'most_recent' | 'prefer_upload' | 'prefer_external' | 'first';
    recommended_keeper_asset_id: string | null;
    selected_keeper_asset_id: string | null;
    selected_action: 'automatic' | 'resolve' | 'keep_all' | 'delete_all' | 'stack_all' | 'mixed' | 'none';
    member_decisions: Record<string, DuplicateDisposition>;
    stack_primary_asset_id: string | null;
    recommendation_reason_codes: string[];
    members: Array<DuplicatePreviewMember & {
      verification: 'matching' | 'mismatch' | 'unverified';
      content_checksum: string | null;
    }>;
    initial_index: number;
    onmemberdispositionchange?: (assetId: string, disposition: DuplicateDisposition) => void;
    onstackprimarychange?: (assetId: string) => void;
    onsimilarityreferencechange?: (assetId: string) => Promise<Array<DuplicatePreviewMember & {
      verification: 'matching' | 'mismatch' | 'unverified';
      content_checksum: string | null;
    }>>;
    onpreviousgroup?: () => void;
    onnextgroup?: () => void;
  }

  interface Props {
    review: DuplicatePreviewReview;
    onclose: () => void;
  }

  let { review, onclose }: Props = $props();
  let similarityMembers = $state.raw<DuplicatePreviewReview['members'] | null>(null);
  const members = $derived(similarityMembers ?? review.members);
  let viewerIndex = $state(0);
  let detail = $state.raw<AssetDetail | null>(null);
  let integrity = $state.raw<AssetIntegrityState | null>(null);
  let detailLoading = $state(true);
  let detailError = $state<string | null>(null);
  let detailGeneration = 0;
  let selectedKeeperId = $state<string | null>(null);
  let selectedAction = $state<DuplicatePreviewReview['selected_action']>('automatic');
  let memberDecisions = $state<Record<string, DuplicateDisposition>>({});
  let stackPrimaryAssetId = $state<string | null>(null);
  let similarityLoading = $state(false);
  let similarityError = $state<string | null>(null);
  const selectedIds = new Set<string>();
  const assets = $derived<AssetSummary[]>(members.map((member) => ({
    id: member.id,
    type: member.original_mime_type?.startsWith('video/') ? 'VIDEO' : 'IMAGE',
    original_file_name: member.original_file_name,
    original_mime_type: member.original_mime_type,
    width: null,
    height: null,
    duration: null,
    taken_at: member.file_modified_at,
    file_modified_at: member.file_modified_at,
    is_favorite: false,
    is_archived: false,
    is_trashed: false,
    is_offline: member.is_offline,
    is_edited: false,
    visibility: null,
    has_metadata: false,
    live_photo_video_id: null,
    file_size_bytes: member.file_size_bytes,
    people_count: 0,
    tag_count: 0,
    stack_count: 0,
    albums: [],
    tags: [],
    stack: null,
    source: {
      kind: member.source_kind,
      library_id: member.library_id,
      original_path: null,
    },
    immich_url: member.immich_url,
  })));
  const duplicateContext = $derived<DuplicateReviewContext>({
    group_id: review.group_id,
    discovery_source: review.discovery_source,
    discovery_metadata: review.discovery_metadata,
    classification: review.classification,
    status: review.status,
    reason: review.reason,
    eligible: review.eligible,
    keeper_policy: review.keeper_policy,
    recommended_keeper_asset_id: review.recommended_keeper_asset_id,
    selected_keeper_asset_id: selectedKeeperId,
    selected_action: selectedAction,
    stack_primary_asset_id: stackPrimaryAssetId,
    recommendation_reason_codes: review.recommendation_reason_codes,
    members: members.map((member) => ({
      id: member.id,
      filename: member.original_file_name,
      source_kind: member.source_kind,
      library_id: member.library_id,
      verification: member.verification,
      content_checksum: member.content_checksum,
      file_size_bytes: member.file_size_bytes,
      is_offline: member.is_offline,
      is_stacked: member.is_stacked,
      disposition: memberDecisions[member.id] ?? null,
      recommended_disposition: member.recommended_disposition ?? null,
      recommendation_reason_codes: member.recommendation_reason_codes ?? [],
      similarity: member.similarity,
      preservation: member.preservation,
    })),
    current_integrity: integrity,
    similarity_loading: similarityLoading,
    similarity_error: similarityError,
  });

  async function navigate(index: number): Promise<void> {
    if (index < 0 || index >= members.length) return;
    viewerIndex = index;
    detail = null;
    integrity = null;
    detailError = null;
    detailLoading = true;
    const generation = ++detailGeneration;
    try {
      const [loaded, integrityState] = await Promise.all([
        getAssetDetail(members[index].id),
        getAssetIntegrity(members[index].id),
      ]);
      if (generation === detailGeneration) {
        detail = loaded;
        integrity = integrityState;
      }
    } catch (reason) {
      if (generation === detailGeneration) {
        detailError = reason instanceof Error ? reason.message : 'Could not load live asset details.';
      }
    } finally {
      if (generation === detailGeneration) detailLoading = false;
    }
  }

  function chooseDisposition(assetId: string, disposition: DuplicateDisposition): void {
    memberDecisions = { ...memberDecisions, [assetId]: disposition };
    stackPrimaryAssetId = resolveStackPrimary(
      members
        .filter((member) => memberDecisions[member.id] === 'stack')
        .map((member) => member.id),
      stackPrimaryAssetId,
      [selectedKeeperId, review.recommended_keeper_asset_id],
    );
    review.onmemberdispositionchange?.(assetId, disposition);
  }

  function chooseStackPrimary(assetId: string): void {
    if (memberDecisions[assetId] !== 'stack') return;
    stackPrimaryAssetId = assetId;
    review.onstackprimarychange?.(assetId);
  }

  async function chooseSimilarityReference(assetId: string): Promise<void> {
    if (!review.onsimilarityreferencechange || similarityLoading) return;
    similarityLoading = true;
    similarityError = null;
    try {
      similarityMembers = await review.onsimilarityreferencechange(assetId);
    } catch (reason) {
      similarityError = reason instanceof Error
        ? reason.message
        : 'Could not change the similarity reference.';
    } finally {
      similarityLoading = false;
    }
  }

  onMount(() => {
    selectedKeeperId = review.selected_keeper_asset_id;
    selectedAction = review.selected_action;
    memberDecisions = { ...review.member_decisions };
    stackPrimaryAssetId = review.stack_primary_asset_id;
    void navigate(review.initial_index);
  });
</script>

{#if assets.length}
  <AssetViewerDialog
    {assets}
    initialIndex={viewerIndex}
    {selectedIds}
    {detail}
    {detailLoading}
    {detailError}
    albums={[]}
    tags={[]}
    actionPlan={null}
    actionSummary={null}
    actionsEnabled={false}
    selectionEnabled={false}
    apiOnly={true}
    integrityEnabled={true}
    {duplicateContext}
    onduplicatedisposition={chooseDisposition}
    onduplicatestackprimary={chooseStackPrimary}
    onduplicatesimilarityreference={(assetId) => void chooseSimilarityReference(assetId)}
    onduplicatepreviousgroup={review.onpreviousgroup}
    onduplicatenextgroup={review.onnextgroup}
    comparisonSource="duplicate"
    comparisonActivation="click"
    comparisonAssets={assets}
    onnavigate={(index) => void navigate(index)}
    ontoggleselection={() => {}}
    onvisiblechange={(assetId) => {
      const index = members.findIndex((member) => member.id === assetId);
      if (index >= 0 && index !== viewerIndex) void navigate(index);
    }}
    onaction={() => {}}
    onrelationconfirm={() => {}}
    onconfirmaction={() => {}}
    oncancelaction={() => {}}
    onsync={() => {}}
    {onclose}
  />
{/if}
