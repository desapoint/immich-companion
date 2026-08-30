<script lang="ts">
  import { onMount } from 'svelte';

  import { getAssetDetail, getAssetIntegrity } from '../api/assetApi';
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
  }

  interface DuplicatePreviewReview {
    duplicate_id: string;
    status: 'exact' | 'unverified' | 'mismatch' | 'ineligible';
    reason: string | null;
    eligible: boolean;
    keeper_policy: 'most_recent' | 'prefer_upload' | 'prefer_external' | 'first';
    recommended_keeper_asset_id: string | null;
    selected_keeper_asset_id: string | null;
    selected_action: 'resolve' | 'stack_all' | 'none';
    recommendation_reason_codes: string[];
    members: Array<DuplicatePreviewMember & {
      verification: 'matching' | 'mismatch' | 'unverified';
      content_checksum: string | null;
    }>;
    initial_index: number;
    onkeeperchange?: (assetId: string) => 'resolve' | 'stack_all' | 'none';
    onactionchange?: (action: 'resolve' | 'stack_all' | 'none') => void;
  }

  interface Props {
    review: DuplicatePreviewReview;
    onclose: () => void;
  }

  let { review, onclose }: Props = $props();
  const members = $derived(review.members);
  let viewerIndex = $state(0);
  let detail = $state.raw<AssetDetail | null>(null);
  let integrity = $state.raw<AssetIntegrityState | null>(null);
  let detailLoading = $state(true);
  let detailError = $state<string | null>(null);
  let detailGeneration = 0;
  let selectedKeeperId = $state<string | null>(null);
  let selectedAction = $state<'resolve' | 'stack_all' | 'none'>('none');
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
    duplicate_id: review.duplicate_id,
    status: review.status,
    reason: review.reason,
    eligible: review.eligible,
    keeper_policy: review.keeper_policy,
    recommended_keeper_asset_id: review.recommended_keeper_asset_id,
    selected_keeper_asset_id: selectedKeeperId,
    selected_action: selectedAction,
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
    })),
    current_integrity: integrity,
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

  function chooseKeeper(assetId: string): void {
    selectedKeeperId = assetId;
    selectedAction = review.onkeeperchange?.(assetId) ?? selectedAction;
  }

  function chooseAction(action: 'resolve' | 'stack_all' | 'none'): void {
    selectedAction = action;
    review.onactionchange?.(action);
  }

  onMount(() => {
    selectedKeeperId = review.selected_keeper_asset_id;
    selectedAction = review.selected_action;
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
    onduplicatekeeper={chooseKeeper}
    onduplicateaction={chooseAction}
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
