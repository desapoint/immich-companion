import type { AssetSelectionState } from '../../../v2/components/assetSelection';
import { BASE_ALBUMS, BASE_ALBUM_ASSETS, BASE_STACKS, BASE_TAGS, BASE_TAG_ASSETS, BASE_TRASH_IDS, LEGACY_STORAGE_KEYS, PREVIOUS_STORAGE_KEY, STORAGE_KEY, applyRelationships, baseAssetsById, buildState, cloneAsset, cloneStack, newDemoId, tagValueForPath, toTrashApiAsset } from '../data/demoAssetSeed';
import type { DemoAlbumRecord, DemoAssetOverride, DemoAssetRecord, DemoAssetStackSnapshot, DemoTagAssetRecord, DemoTagRecord, DemoTrashApiAsset, DemoTrashRelationshipSnapshot, PersistedDemoState, PersistedDemoStateV3 } from '../data/demoAssetTypes';

const initialState = buildState(BASE_TRASH_IDS);
export const demoAssetState = $state({
  assets: initialState.assets, trash_api_items: initialState.trash_api_items, albums: initialState.albums, album_assets: initialState.album_assets,
  tags: initialState.tags, tag_assets: initialState.tag_assets, trash_relationships: initialState.trash_relationships, initialized: false, revision: 0,
});

function currentStacks(): Record<string, DemoAssetStackSnapshot | null> {
  const stacks: Record<string, DemoAssetStackSnapshot | null> = {};
  for (const asset of demoAssetState.assets) stacks[asset.id] = cloneStack(asset.stack);
  return stacks;
}

function refreshRelationshipSummaries(): void {
  const relationships = applyRelationships(demoAssetState.assets, demoAssetState.albums, demoAssetState.tags, demoAssetState.album_assets, demoAssetState.tag_assets, currentStacks());
  demoAssetState.albums = relationships.albums;
  demoAssetState.tags = relationships.tags;
}

function persist(): void {
  demoAssetState.revision += 1;
  if (typeof sessionStorage === 'undefined') return;
  const overrides: Record<string, DemoAssetOverride> = {};
  for (const asset of [...demoAssetState.assets, ...demoAssetState.trash_api_items]) {
    const base = baseAssetsById.get(asset.id);
    if (base && (asset.is_favorite !== base.is_favorite || asset.is_archived !== base.is_archived)) overrides[asset.id] = { is_favorite: asset.is_favorite, is_archived: asset.is_archived };
  }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
    version: 4, asset_overrides: overrides, trash_api_ids: demoAssetState.trash_api_items.map((asset) => asset.id), albums: demoAssetState.albums,
    tags: demoAssetState.tags, album_assets: demoAssetState.album_assets, tag_assets: demoAssetState.tag_assets, trash_relationships: demoAssetState.trash_relationships,
    stacks: currentStacks(),
  } satisfies PersistedDemoState));
}

export function initializeDemoAssetState(): void {
  if (demoAssetState.initialized) return;
  demoAssetState.initialized = true;
  if (typeof sessionStorage === 'undefined') return;
  for (const key of LEGACY_STORAGE_KEYS) sessionStorage.removeItem(key);
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY) ?? sessionStorage.getItem(PREVIOUS_STORAGE_KEY);
    if (!raw) return;
    const persisted = JSON.parse(raw) as PersistedDemoState | PersistedDemoStateV3;
    if ((persisted.version !== 4 && persisted.version !== 3) || !Array.isArray(persisted.trash_api_ids)) return;
    const rebuilt = buildState(
      new Set(persisted.trash_api_ids),
      persisted.version === 4 && Array.isArray(persisted.albums) ? persisted.albums : BASE_ALBUMS,
      persisted.version === 4 && Array.isArray(persisted.tags) ? persisted.tags : BASE_TAGS,
      Array.isArray(persisted.album_assets) ? persisted.album_assets : BASE_ALBUM_ASSETS,
      Array.isArray(persisted.tag_assets) ? persisted.tag_assets : BASE_TAG_ASSETS,
      persisted.stacks ?? BASE_STACKS,
      persisted.version === 4 ? persisted.trash_relationships ?? {} : {},
    );
    for (const asset of [...rebuilt.assets, ...rebuilt.trash_api_items]) {
      const override = persisted.asset_overrides?.[asset.id];
      if (override) { asset.is_favorite = Boolean(override.is_favorite); asset.is_archived = Boolean(override.is_archived); }
    }
    demoAssetState.assets = rebuilt.assets; demoAssetState.trash_api_items = rebuilt.trash_api_items; demoAssetState.albums = rebuilt.albums; demoAssetState.album_assets = rebuilt.album_assets;
    demoAssetState.tags = rebuilt.tags; demoAssetState.tag_assets = rebuilt.tag_assets; demoAssetState.trash_relationships = rebuilt.trash_relationships; demoAssetState.revision += 1;
    if (persisted.version === 3) persist();
  } catch { sessionStorage.removeItem(STORAGE_KEY); }
}

export function resetDemoAssetState(): void {
  const rebuilt = buildState(BASE_TRASH_IDS);
  demoAssetState.assets = rebuilt.assets; demoAssetState.trash_api_items = rebuilt.trash_api_items; demoAssetState.albums = rebuilt.albums; demoAssetState.album_assets = rebuilt.album_assets;
  demoAssetState.tags = rebuilt.tags; demoAssetState.tag_assets = rebuilt.tag_assets; demoAssetState.trash_relationships = rebuilt.trash_relationships; demoAssetState.revision += 1;
  if (typeof sessionStorage !== 'undefined') { sessionStorage.removeItem(STORAGE_KEY); sessionStorage.removeItem(PREVIOUS_STORAGE_KEY); for (const key of LEGACY_STORAGE_KEYS) sessionStorage.removeItem(key); }
}

export function indexedDemoAssets(): DemoAssetRecord[] { return demoAssetState.assets; }
export function trashApiDemoAssets(): DemoTrashApiAsset[] { return demoAssetState.trash_api_items; }
export function demoAssetById(id: string): DemoAssetRecord | undefined { return demoAssetState.assets.find((asset) => asset.id === id); }
export function selectedDemoAssetIds(selection: AssetSelectionState<string>, matchingIds: readonly string[]): string[] { return selection.allMatchingSelected ? matchingIds.filter((id) => !selection.excludedIds.has(id)) : matchingIds.filter((id) => selection.selectedIds.has(id)); }

function mutateIndexedAssets(ids: readonly string[], mutate: (asset: DemoAssetRecord) => void): void { const idSet = new Set(ids); for (const asset of demoAssetState.assets) if (idSet.has(asset.id)) mutate(asset); persist(); }
export function setDemoAssetsFavorite(ids: readonly string[], favorite: boolean): void { mutateIndexedAssets(ids, (asset) => { asset.is_favorite = favorite; }); }
export function setDemoAssetsArchived(ids: readonly string[], archived: boolean): void { mutateIndexedAssets(ids, (asset) => { asset.is_archived = archived; }); }
export function syncDemoAssets(ids: readonly string[]): void { const now = new Date().toISOString(); mutateIndexedAssets(ids, (asset) => { asset.synced_at = now; }); }

export function createDemoAlbum(name: string, description = ''): DemoAlbumRecord | undefined {
  const trimmed = name.trim(); if (!trimmed) return undefined; const now = new Date().toISOString();
  const album: DemoAlbumRecord = { id: newDemoId('album'), album_name: trimmed, description: description.trim(), album_thumbnail_asset_id: null, asset_count: 0, immich_created_at: now, immich_updated_at: now, synced_at: now };
  demoAssetState.albums = [...demoAssetState.albums, album]; persist(); return album;
}
export function updateDemoAlbum(id: string, patch: { name?: string; description?: string }): void { const now = new Date().toISOString(); demoAssetState.albums = demoAssetState.albums.map((album) => album.id === id ? { ...album, album_name: patch.name?.trim() || album.album_name, description: patch.description?.trim() ?? album.description, immich_updated_at: now, synced_at: now } : album); persist(); }
export function deleteDemoAlbums(ids: readonly string[]): void { const idSet = new Set(ids); demoAssetState.albums = demoAssetState.albums.filter((album) => !idSet.has(album.id)); demoAssetState.album_assets = demoAssetState.album_assets.filter((membership) => !idSet.has(membership.album_id)); refreshRelationshipSummaries(); persist(); }
export function addDemoAssetsToAlbum(assetIds: readonly string[], albumId: string): void { const validAssets = new Set(demoAssetState.assets.map((asset) => asset.id)), existing = new Set(demoAssetState.album_assets.map((membership) => `${membership.album_id}:${membership.asset_id}`)); const additions = assetIds.filter((id) => validAssets.has(id) && !existing.has(`${albumId}:${id}`)).map((asset_id) => ({ album_id: albumId, asset_id })); if (!demoAssetState.albums.some((album) => album.id === albumId) || additions.length === 0) return; demoAssetState.album_assets = [...demoAssetState.album_assets, ...additions]; refreshRelationshipSummaries(); persist(); }
export function removeDemoAssetsFromAlbums(assetIds: readonly string[], albumIds?: readonly string[]): void { const assetSet = new Set(assetIds), albumSet = albumIds ? new Set(albumIds) : null; demoAssetState.album_assets = demoAssetState.album_assets.filter((membership) => !(assetSet.has(membership.asset_id) && (!albumSet || albumSet.has(membership.album_id)))); refreshRelationshipSummaries(); persist(); }

export function createDemoTag(name: string, color: string | null = null, parentPath = ''): DemoTagRecord | undefined { const leaf = name.trim(); if (!leaf) return undefined; const path = parentPath.trim() ? `${parentPath.trim()} / ${leaf}` : leaf; if (demoAssetState.tags.some((tag) => tag.tag_name.toLocaleLowerCase() === path.toLocaleLowerCase())) return undefined; const now = new Date().toISOString(); const tag: DemoTagRecord = { id: newDemoId('tag'), tag_name: path, tag_value: tagValueForPath(path), color, asset_count: 0, synced_at: now }; demoAssetState.tags = [...demoAssetState.tags, tag]; persist(); return tag; }
export function updateDemoTag(id: string, patch: { color?: string | null }): void { const target = demoAssetState.tags.find((tag) => tag.id === id); if (!target) return; const now = new Date().toISOString(); demoAssetState.tags = demoAssetState.tags.map((tag) => tag.id === id ? { ...tag, color: patch.color === undefined ? tag.color : patch.color, synced_at: now } : tag); refreshRelationshipSummaries(); persist(); }
export function deleteDemoTags(ids: readonly string[]): void { const roots = demoAssetState.tags.filter((tag) => ids.includes(tag.id)).map((tag) => tag.tag_name); const deleting = new Set(demoAssetState.tags.filter((tag) => ids.includes(tag.id) || roots.some((root) => tag.tag_name.startsWith(`${root} / `))).map((tag) => tag.id)); demoAssetState.tags = demoAssetState.tags.filter((tag) => !deleting.has(tag.id)); demoAssetState.tag_assets = demoAssetState.tag_assets.filter((membership) => !deleting.has(membership.tag_id)); refreshRelationshipSummaries(); persist(); }
export function addDemoTagsToAssets(assetIds: readonly string[], tagIds: readonly string[]): void { const validAssets = new Set(demoAssetState.assets.map((asset) => asset.id)), validTags = new Set(demoAssetState.tags.map((tag) => tag.id)), existing = new Set(demoAssetState.tag_assets.map((membership) => `${membership.tag_id}:${membership.asset_id}`)); const additions: DemoTagAssetRecord[] = []; for (const asset_id of assetIds) for (const tag_id of tagIds) if (validAssets.has(asset_id) && validTags.has(tag_id) && !existing.has(`${tag_id}:${asset_id}`)) additions.push({ tag_id, asset_id }); if (additions.length === 0) return; demoAssetState.tag_assets = [...demoAssetState.tag_assets, ...additions]; refreshRelationshipSummaries(); persist(); }
export function removeDemoTagsFromAssets(assetIds: readonly string[], tagIds?: readonly string[]): void { const assetSet = new Set(assetIds), tagSet = tagIds ? new Set(tagIds) : null; demoAssetState.tag_assets = demoAssetState.tag_assets.filter((membership) => !(assetSet.has(membership.asset_id) && (!tagSet || tagSet.has(membership.tag_id)))); refreshRelationshipSummaries(); persist(); }

export function stackDemoAssets(ids: readonly string[]): void { const valid = [...new Set(ids)].filter((id) => demoAssetState.assets.some((asset) => asset.id === id)); if (valid.length < 2) return; removeDemoAssetsFromStacks(valid, false); const stack: DemoAssetStackSnapshot = { id: newDemoId('stack'), primaryAssetId: valid[0], assetCount: valid.length, assets: valid }; for (const asset of demoAssetState.assets) if (valid.includes(asset.id)) asset.stack = cloneStack(stack); persist(); }
export function setDemoStackPrimary(assetId: string): void { const asset = demoAssetById(assetId), stack = asset?.stack; if (!stack) return; for (const item of demoAssetState.assets) if (item.stack?.id === stack.id) item.stack = { ...item.stack, primaryAssetId: assetId }; persist(); }
export function removeDemoAssetsFromStacks(ids: readonly string[], persistChange = true): void { const idSet = new Set(ids), affectedStackIds = new Set(demoAssetState.assets.filter((asset) => idSet.has(asset.id) && asset.stack).map((asset) => asset.stack!.id)); for (const stackId of affectedStackIds) { const members = demoAssetState.assets.filter((asset) => asset.stack?.id === stackId && !idSet.has(asset.id)); const primary = members.find((asset) => asset.stack?.primaryAssetId === asset.id)?.id ?? members[0]?.id; for (const asset of demoAssetState.assets) { if (asset.stack?.id !== stackId) continue; if (idSet.has(asset.id) || members.length < 2) asset.stack = null; else asset.stack = { ...asset.stack, assets: members.map((member) => member.id), assetCount: members.length, primaryAssetId: primary! }; } } if (persistChange) persist(); }
export function removeDemoCompleteStack(assetId: string): void { const stackId = demoAssetById(assetId)?.stack?.id; if (!stackId) return; for (const asset of demoAssetState.assets) if (asset.stack?.id === stackId) asset.stack = null; persist(); }

export function trashDemoAssets(ids: readonly string[]): void { const idSet = new Set(ids), moving = demoAssetState.assets.filter((asset) => idSet.has(asset.id)); if (moving.length === 0) return; for (const asset of moving) demoAssetState.trash_relationships[asset.id] = { album_ids: demoAssetState.album_assets.filter((membership) => membership.asset_id === asset.id).map((membership) => membership.album_id), tag_ids: demoAssetState.tag_assets.filter((membership) => membership.asset_id === asset.id).map((membership) => membership.tag_id), stack: cloneStack(asset.stack) }; demoAssetState.assets = demoAssetState.assets.filter((asset) => !idSet.has(asset.id)); demoAssetState.trash_api_items = [...demoAssetState.trash_api_items, ...moving.map(toTrashApiAsset)]; demoAssetState.album_assets = demoAssetState.album_assets.filter((membership) => !idSet.has(membership.asset_id)); demoAssetState.tag_assets = demoAssetState.tag_assets.filter((membership) => !idSet.has(membership.asset_id)); refreshRelationshipSummaries(); persist(); }
export function restoreDemoTrashAssets(ids: readonly string[]): void { const idSet = new Set(ids), restoring = demoAssetState.trash_api_items.filter((asset) => idSet.has(asset.id)); if (restoring.length === 0) return; demoAssetState.trash_api_items = demoAssetState.trash_api_items.filter((asset) => !idSet.has(asset.id)); const existing = new Set(demoAssetState.assets.map((asset) => asset.id)); for (const item of restoring) { if (existing.has(item.id)) continue; const base = baseAssetsById.get(item.id); if (!base) continue; const refreshed = cloneAsset(base); refreshed.is_favorite = item.is_favorite; refreshed.is_archived = item.is_archived; refreshed.synced_at = new Date().toISOString(); const snapshot = demoAssetState.trash_relationships[item.id] as DemoTrashRelationshipSnapshot | undefined; refreshed.stack = cloneStack(snapshot?.stack ?? null); demoAssetState.assets.push(refreshed); if (snapshot) { demoAssetState.album_assets.push(...snapshot.album_ids.filter((albumId: string) => demoAssetState.albums.some((album) => album.id === albumId)).map((album_id: string) => ({ album_id, asset_id: item.id }))); demoAssetState.tag_assets.push(...snapshot.tag_ids.filter((tagId: string) => demoAssetState.tags.some((tag) => tag.id === tagId)).map((tag_id: string) => ({ tag_id, asset_id: item.id }))); delete demoAssetState.trash_relationships[item.id]; } } refreshRelationshipSummaries(); persist(); }
