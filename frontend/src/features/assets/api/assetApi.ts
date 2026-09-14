import type {
  AssetDetail,
  AssetActionIntent,
  AssetActionPlan,
  AssetActionResult,
  AssetActionTaskStart,
  AlbumOption,
  AssetSearchResponse,
  AssetSummary,
  AssetSelectionRequest,
  AssetSelectionResolution,
  AssetSelectionSyncResult,
  AssetSort,
  AssetSyncResult,
  AssetSyncCoordinatorStatus,
  AssetSyncMode,
  AssetSyncRunStatus,
  AssetTaskStatus,
  SelectionSetMembershipResponse,
  SelectionSetView,
  SearchGroup,
  AssetViewerMedia,
  AssetIntegrityAnalyzeResponse,
  AssetIntegrityState,
  TagOption,
  StackResolution,
} from '../types/assets';
import type { MediaPreviewItem } from '../../../lib/types/media';
import { ApiError, requestJson, requestVoid } from '../../shared/api/http';
import { createDefaultAssetSort } from '../state/assetSort';
import { serializeSearchGroup } from '../state/assetViewModel';
import { DEFAULT_ASSET_PAGE_SIZE } from '../state/assetPagination';
import { RevisionedMutationQueue } from '../state/revisionedMutationQueue';

const selectionMutationQueue = new RevisionedMutationQueue<SelectionSetView>();

function throwIfAborted(signal?: AbortSignal): void {
  if (signal?.aborted) throw new DOMException('Aborted', 'AbortError');
}

async function settleSelection(selectionId: string | null | undefined, signal?: AbortSignal): Promise<void> {
  if (!selectionId) return;
  await selectionMutationQueue.waitForIdle(selectionId);
  throwIfAborted(signal);
}

export function isAssetSelectionUnavailableError(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  const detail = (error.detail ?? error.message).toLowerCase();
  return detail.includes('selection set')
    && (detail.includes('expired') || detail.includes('not found'));
}

export function isTaskUnavailableError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

export function openTaskStream(
  taskId: string,
  onstatus: (task: AssetTaskStatus) => void,
  onerror?: () => void,
  onclose?: () => void,
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(
    `${protocol}//${window.location.host}/api/tasks/${encodeURIComponent(taskId)}/stream`,
  );
  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as AssetTaskStatus;
      if (payload.id) onstatus(payload);
    } catch {
      onerror?.();
    }
  };
  socket.onerror = () => onerror?.();
  socket.onclose = () => onclose?.();
  return socket;
}

export function openTaskUpdates(
  onstatus: (task: AssetTaskStatus) => void,
  onerror?: () => void,
  onclose?: () => void,
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const socket = new WebSocket(`${protocol}//${window.location.host}/api/tasks/stream`);
  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as AssetTaskStatus;
      if (payload.id) onstatus(payload);
    } catch {
      onerror?.();
    }
  };
  socket.onerror = () => onerror?.();
  socket.onclose = () => onclose?.();
  return socket;
}

export function normalizeAssetSummary(asset: AssetSummary): AssetSummary {
  return {
    ...asset,
    albums: asset.albums ?? [],
    tags: asset.tags ?? [],
    stack: asset.stack
      ? { ...asset.stack, assets: asset.stack.assets ?? [] }
      : null,
    source: asset.source ?? { kind: 'upload', library_id: null, original_path: null },
    immich_url: asset.immich_url ?? null,
  };
}

export function normalizeAssetSearchResponse(response: AssetSearchResponse): AssetSearchResponse {
  return {
    ...response,
    items: response.items.map(normalizeAssetSummary),
  };
}

export function buildAssetSearchRequest(
  expression: SearchGroup,
  page: number,
  pageSize = DEFAULT_ASSET_PAGE_SIZE,
  sort: AssetSort = createDefaultAssetSort(),
  selectionId?: string | null,
): Record<string, unknown> {
  return {
    expression: serializeSearchGroup(expression),
    sort_field: sort.field,
    sort_direction: sort.direction,
    page,
    page_size: pageSize,
    ...(selectionId ? { selection_id: selectionId } : {}),
  };
}

export async function searchAssets(
  expression: SearchGroup,
  page: number,
  pageSize = DEFAULT_ASSET_PAGE_SIZE,
  sort: AssetSort = createDefaultAssetSort(),
  signal?: AbortSignal,
  selectionId?: string | null,
): Promise<AssetSearchResponse> {
  await settleSelection(selectionId, signal);
  const response = await requestJson<AssetSearchResponse>('/api/assets/search', {
    method: 'POST',
    json: buildAssetSearchRequest(expression, page, pageSize, sort, selectionId),
    signal,
  });
  return normalizeAssetSearchResponse(response);
}

export async function matchAssetSearch(
  assetId: string,
  expression: SearchGroup,
  signal?: AbortSignal,
): Promise<AssetSummary | null> {
  const asset = await requestJson<AssetSummary | null>(
    `/api/assets/${encodeURIComponent(assetId)}/search-match`,
    {
      method: 'POST',
      json: { expression: serializeSearchGroup(expression) },
      signal,
    },
  );
  return asset ? normalizeAssetSummary(asset) : null;
}

export function getAlbumOptions(signal?: AbortSignal): Promise<AlbumOption[]> {
  return requestJson('/api/albums', { signal });
}

export function getTagOptions(signal?: AbortSignal): Promise<TagOption[]> {
  return requestJson('/api/tags', { signal });
}

export function createAlbum(name: string, description = ''): Promise<AlbumOption> {
  return requestJson('/api/albums/manage', {
    method: 'POST',
    json: { name, description },
  });
}

export function createTag(name: string, color: string | null = null): Promise<TagOption> {
  return requestJson('/api/tags/manage', {
    method: 'POST',
    json: { name, color },
  });
}

export function synchronizeAssets(): Promise<AssetSyncResult> {
  return requestJson('/api/assets/sync', { method: 'POST' });
}

export function startAssetSync(mode: AssetSyncMode): Promise<AssetSyncRunStatus> {
  return requestJson('/api/assets/sync/start', {
    method: 'POST',
    json: { mode },
  });
}

export function getAssetSyncStatus(signal?: AbortSignal): Promise<AssetSyncCoordinatorStatus> {
  return requestJson('/api/assets/sync/status', { signal });
}

export function getTaskStatus(taskId: string, signal?: AbortSignal): Promise<AssetTaskStatus> {
  return requestJson(`/api/tasks/${encodeURIComponent(taskId)}`, { signal });
}

export function cancelTask(taskId: string): Promise<AssetTaskStatus> {
  return requestJson(`/api/tasks/${encodeURIComponent(taskId)}/cancel`, { method: 'POST' });
}

export function listTasks(taskType: string, limit = 10): Promise<AssetTaskStatus[]> {
  return requestJson(`/api/tasks?task_type=${encodeURIComponent(taskType)}&limit=${limit}`);
}

export async function resolveAssetSelection(
  selection: AssetSelectionRequest,
  signal?: AbortSignal,
): Promise<AssetSelectionResolution> {
  await settleSelection(selection.selection_id, signal);
  return requestJson('/api/assets/selection/resolve', {
    method: 'POST',
    json: selection,
    signal,
  });
}

export function materializeAssetSelection(
  expression: SearchGroup,
  signal?: AbortSignal,
): Promise<string[]> {
  return requestJson('/api/assets/selection/ids', {
    method: 'POST',
    json: {
      mode: 'all_matching',
      ids: [],
      expression: serializeSearchGroup(expression),
      excluded_ids: [],
    },
    signal,
  });
}

export function createAssetSelection(signal?: AbortSignal): Promise<SelectionSetView> {
  return requestJson('/api/assets/selections', {
    method: 'POST',
    json: {},
    signal,
  });
}

export function selectAllAssetSelection(
  selectionId: string,
  expression: SearchGroup,
  signal?: AbortSignal,
): Promise<SelectionSetView> {
  return requestJson(`/api/assets/selections/${encodeURIComponent(selectionId)}/select-all`, {
    method: 'POST',
    json: { expression: serializeSearchGroup(expression) },
    signal,
  });
}

export function updateAssetSelectionMembers(
  selectionId: string,
  assetIds: string[],
  selected: boolean,
  revision: number,
): Promise<SelectionSetView> {
  return selectionMutationQueue.enqueue(selectionId, revision, (effectiveRevision) => (
    requestJson(`/api/assets/selections/${encodeURIComponent(selectionId)}/members`, {
      method: 'POST',
      json: { asset_ids: assetIds, selected, revision: effectiveRevision },
    })
  ));
}

export function waitForAssetSelectionMutations(selectionId: string): Promise<void> {
  return selectionMutationQueue.waitForIdle(selectionId);
}

export async function getAssetSelectionMembership(
  selectionId: string,
  assetIds: string[],
  signal?: AbortSignal,
): Promise<SelectionSetMembershipResponse> {
  await settleSelection(selectionId, signal);
  return requestJson(`/api/assets/selections/${encodeURIComponent(selectionId)}/membership`, {
    method: 'POST',
    json: { asset_ids: assetIds },
    signal,
  });
}

export async function planAssetAction(
  selection: AssetSelectionRequest,
  action: AssetActionIntent,
  relationIds: string[] = [],
  stackResolution?: StackResolution,
  stackPrimaryAssetId?: string,
  signal?: AbortSignal,
): Promise<AssetActionPlan> {
  await settleSelection(selection.selection_id, signal);
  return requestJson('/api/assets/actions/plan', {
    method: 'POST',
    json: {
      selection,
      action,
      relation_ids: relationIds,
      ...(stackResolution ? { stack_resolution: stackResolution } : {}),
      ...(stackPrimaryAssetId ? { stack_primary_asset_id: stackPrimaryAssetId } : {}),
    },
    signal,
  });
}

export function executeAssetAction(planId: string): Promise<AssetActionResult> {
  return requestJson('/api/assets/actions/execute', {
    method: 'POST',
    json: { plan_id: planId, confirm: true },
  });
}

export function executeAssetActionTask(planId: string): Promise<AssetActionTaskStart> {
  return requestJson('/api/assets/actions/execute-task', {
    method: 'POST',
    json: { plan_id: planId, confirm: true },
  });
}

export function getAssetDetail(assetId: string, signal?: AbortSignal): Promise<AssetDetail> {
  return requestJson(`/api/assets/${encodeURIComponent(assetId)}`, { signal });
}

export function getAssetIntegrity(
  assetId: string,
  signal?: AbortSignal,
): Promise<AssetIntegrityState> {
  return requestJson(`/api/assets/${encodeURIComponent(assetId)}/integrity`, { signal });
}

export function analyzeAssetIntegrity(
  assetId: string,
  force = false,
  signal?: AbortSignal,
): Promise<AssetIntegrityAnalyzeResponse> {
  return requestJson(`/api/assets/${encodeURIComponent(assetId)}/integrity/analyze`, {
    method: 'POST',
    json: { force },
    signal,
  });
}

export function getRestoreAssetDetail(assetId: string, signal?: AbortSignal): Promise<AssetDetail> {
  return requestJson(`/api/restore/${encodeURIComponent(assetId)}`, { signal });
}

export async function getRestoreAssets(
  page: number,
  pageSize = 48,
  signal?: AbortSignal,
): Promise<AssetSearchResponse> {
  const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  const response = await requestJson<AssetSearchResponse>(`/api/restore?${query}`, { signal });
  return normalizeAssetSearchResponse(response);
}

export function restoreAsset(assetId: string): Promise<void> {
  return requestVoid(`/api/restore/${encodeURIComponent(assetId)}`, { method: 'POST' });
}

export function restoreAssets(
  target: { ids: string[] } | { all: true },
): Promise<{ restored: number }> {
  return requestJson('/api/restore', {
    method: 'POST',
    json: target,
  });
}

export function getAssetSummary(assetId: string, signal?: AbortSignal): Promise<AssetSummary | null> {
  return requestJson(`/api/assets/${encodeURIComponent(assetId)}/summary`, { signal });
}

export function synchronizeAsset(assetId: string): Promise<AssetDetail> {
  return requestJson(`/api/assets/${encodeURIComponent(assetId)}/sync`, { method: 'POST' });
}

export async function synchronizeAssetSelection(
  selection: AssetSelectionRequest,
): Promise<AssetSelectionSyncResult> {
  await settleSelection(selection.selection_id);
  return requestJson('/api/assets/sync/selection', {
    method: 'POST',
    json: selection,
  });
}

export function assetMediaUrl(
  assetId: string,
  size: 'thumbnail' | 'preview' | 'fullsize',
): string {
  return `/api/assets/${encodeURIComponent(assetId)}/thumbnail?size=${size}`;
}

export function assetOriginalUrl(assetId: string): string {
  return `/api/assets/${encodeURIComponent(assetId)}/original`;
}

export function buildAssetPreviewItems(
  assets: AssetViewerMedia[],
  primaryAssetId?: string,
): MediaPreviewItem[] {
  return assets.map((asset) => ({
    id: asset.id,
    label: asset.original_file_name,
    thumbnailUrl: assetMediaUrl(asset.id, 'thumbnail'),
    meta: asset.width && asset.height
      ? `${asset.type} · ${asset.width} × ${asset.height}`
      : asset.type,
    ...(primaryAssetId !== undefined ? { isPrimary: asset.id === primaryAssetId } : {}),
  }));
}
