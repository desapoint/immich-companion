import {
  addDemoAssetsToAlbum,
  addDemoTagsToAssets,
  createDemoAlbum,
  createDemoTag,
  deleteDemoAlbums,
  deleteDemoTags,
  demoAssetById,
  demoAssetState,
  indexedDemoAssets,
  initializeDemoAssetState,
  removeDemoAssetsFromAlbums,
  removeDemoAssetsFromStacks,
  removeDemoCompleteStack,
  removeDemoTagsFromAssets,
  restoreDemoTrashAssets,
  setDemoAssetsArchived,
  setDemoAssetsFavorite,
  setDemoStackPrimary,
  stackDemoAssets,
  syncDemoAssets,
  trashApiDemoAssets,
  trashDemoAssets,
  updateDemoAlbum,
  updateDemoTag,
} from '../../demo/demoAssetState.svelte';
import { demoAssetFullSize, demoAssetPreview } from '../../demo/demoAssetVisuals';
import { demoDifferenceMask } from '../../demo/duplicateVisuals';
import type { AlbumRecord, AssetRecord, AssetSearchGroup, AssetSearchQuery, AssetSearchRule, LibraryDataSource, MutationResult, TagRecord } from '../contracts';

function result(ids: readonly string[], failed: MutationResult['failed'] = []): MutationResult {
  return { affectedIds: [...new Set(ids)], failed };
}

function existingAssetIds(ids: readonly string[]): string[] {
  const valid = new Set(demoAssetState.assets.map((asset) => asset.id));
  return [...new Set(ids)].filter((id) => valid.has(id));
}

function existingTrashIds(ids: readonly string[]): string[] {
  const valid = new Set(demoAssetState.trash_api_items.map((asset) => asset.id));
  return [...new Set(ids)].filter((id) => valid.has(id));
}

function seedFor(id: string): number {
  let hash = 0;
  for (let index = 0; index < id.length; index += 1) hash = (Math.imul(hash, 31) + id.charCodeAt(index)) | 0;
  return Math.abs(hash);
}

function parseRatio(value: string | undefined): number | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  if (trimmed.includes(':')) {
    const [a, b] = trimmed.split(':').map(Number);
    return Number.isFinite(a) && Number.isFinite(b) && b !== 0 ? a / b : undefined;
  }
  const number = Number(trimmed);
  return Number.isFinite(number) ? number : undefined;
}

function albumIdsFor(assetId: string): string[] {
  return demoAssetState.album_assets.filter((membership) => membership.asset_id === assetId).map((membership) => membership.album_id);
}

function tagIdsFor(assetId: string): string[] {
  return demoAssetState.tag_assets.filter((membership) => membership.asset_id === assetId).map((membership) => membership.tag_id);
}

function matchesSimple(asset: AssetRecord, query: Extract<AssetSearchQuery, { mode: 'simple' }>): boolean {
  const filters = query.filters;
  if (filters.filename && !asset.original_file_name.toLocaleLowerCase().includes(filters.filename.toLocaleLowerCase())) return false;
  if (filters.mediaType && asset.asset_type !== (filters.mediaType === 'Video' ? 'VIDEO' : 'IMAGE')) return false;
  if (filters.favorite === 'Favorite' && !asset.is_favorite) return false;
  if (filters.favorite === 'Not favorite' && asset.is_favorite) return false;
  if (filters.archived === 'Archived' && !asset.is_archived) return false;
  if (filters.archived === 'Not archived' && asset.is_archived) return false;

  const assetAlbums = albumIdsFor(asset.id);
  const assetTags = tagIdsFor(asset.id);
  if (filters.albumIds?.length && !filters.albumIds.some((id) => assetAlbums.includes(id))) return false;
  if (filters.noAlbum && assetAlbums.length) return false;
  if (filters.tagIds?.length && !filters.tagIds.some((id) => assetTags.includes(id))) return false;
  if (filters.noTag && assetTags.length) return false;

  const date = asset.file_created_at.slice(0, 10);
  if (filters.takenAfter && date < filters.takenAfter) return false;
  if (filters.takenBefore && date > filters.takenBefore) return false;
  if (filters.minWidth && Number(asset.width ?? 0) < Number(filters.minWidth)) return false;
  if (filters.maxWidth && Number(asset.width ?? 0) > Number(filters.maxWidth)) return false;
  if (filters.minHeight && Number(asset.height ?? 0) < Number(filters.minHeight)) return false;
  if (filters.maxHeight && Number(asset.height ?? 0) > Number(filters.maxHeight)) return false;

  const ratio = asset.width && asset.height ? asset.width / asset.height : 0;
  const minRatio = parseRatio(filters.minAspectRatio);
  const maxRatio = parseRatio(filters.maxAspectRatio);
  if (minRatio !== undefined && ratio < minRatio) return false;
  if (maxRatio !== undefined && ratio > maxRatio) return false;
  return true;
}

function comparable(asset: AssetRecord, field: string): string | number | boolean {
  if (field === 'filename') return asset.original_file_name;
  if (field === 'mediaType') return asset.asset_type === 'VIDEO' ? 'Video' : 'Image';
  if (field === 'favorite') return asset.is_favorite;
  if (field === 'archived') return asset.is_archived;
  if (field === 'album') return albumIdsFor(asset.id).map((id) => demoAssetState.albums.find((album) => album.id === id)?.album_name ?? '').join(' | ');
  if (field === 'tag') return asset.tags.map((tag) => tag.name).join(' | ');
  if (field === 'takenDate') return asset.file_created_at.slice(0, 10);
  if (field === 'width') return asset.width ?? 0;
  if (field === 'height') return asset.height ?? 0;
  if (field === 'aspectRatio') return asset.width && asset.height ? asset.width / asset.height : 0;
  return '';
}

function evaluateRule(asset: AssetRecord, rule: AssetSearchRule): boolean {
  const actual = comparable(asset, rule.field);
  const expected = rule.value.trim();
  if (typeof actual === 'boolean') {
    const truth = ['true', 'favorite', 'archived'].includes(expected.toLocaleLowerCase());
    return rule.op === 'isNot' ? actual !== truth : actual === truth;
  }
  if (typeof actual === 'number') {
    const target = parseRatio(expected) ?? Number(expected);
    if (!Number.isFinite(target)) return false;
    if (rule.op === 'gt') return actual > target;
    if (rule.op === 'gte') return actual >= target;
    if (rule.op === 'lt') return actual < target;
    if (rule.op === 'lte') return actual <= target;
    if (rule.op === 'isNot') return actual !== target;
    return actual === target;
  }
  const left = actual.toLocaleLowerCase();
  const right = expected.toLocaleLowerCase();
  if (rule.op === 'contains') return left.includes(right);
  if (rule.op === 'notContains') return !left.includes(right);
  if (rule.op === 'isNot') return left !== right;
  return left.includes(right);
}

function evaluateGroup(asset: AssetRecord, rules: AssetSearchRule[], logic: 'AND' | 'OR', negated = false): boolean {
  const matched = rules.length === 0 ? true : logic === 'AND' ? rules.every((rule) => evaluateRule(asset, rule)) : rules.some((rule) => evaluateRule(asset, rule));
  return negated ? !matched : matched;
}

function matchesExpert(asset: AssetRecord, query: Extract<AssetSearchQuery, { mode: 'expert' }>): boolean {
  const parts = [evaluateGroup(asset, query.rules, query.logic), ...query.groups.map((group: AssetSearchGroup) => evaluateGroup(asset, group.rules, group.logic, group.negated))];
  const matched = query.logic === 'AND' ? parts.every(Boolean) : parts.some(Boolean);
  return query.negated ? !matched : matched;
}

function searchAssets(query: AssetSearchQuery): AssetRecord[] {
  const source = (indexedDemoAssets() as AssetRecord[]).filter((asset) => query.mode === 'simple' ? matchesSimple(asset, query) : matchesExpert(asset, query));
  const multiplier = query.sort.direction === 'desc' ? -1 : 1;
  return [...source].sort((a, b) => query.sort.field === 'filename'
    ? a.original_file_name.localeCompare(b.original_file_name) * multiplier
    : a.file_created_at.localeCompare(b.file_created_at) * multiplier);
}

export function createDemoLibraryDataSource(): LibraryDataSource {
  return {
    kind: 'demo',
    state: {
      get revision() { return demoAssetState.revision; },
      get assets() { return demoAssetState.assets as AssetRecord[]; },
      get trash() { return demoAssetState.trash_api_items; },
      get albums() { return demoAssetState.albums as AlbumRecord[]; },
      get albumAssets() { return demoAssetState.album_assets; },
      get tags() { return demoAssetState.tags as TagRecord[]; },
      get tagAssets() { return demoAssetState.tag_assets; },
    },
    async initialize() { initializeDemoAssetState(); },
    assets: {
      list() { return indexedDemoAssets() as AssetRecord[]; },
      getById(id) { return demoAssetById(id) as AssetRecord | undefined; },
      listTrash() { return trashApiDemoAssets(); },
      async search(query) { const items = searchAssets(query); return { items, total: items.length }; },
      async setFavorite(ids, favorite) { const affected=existingAssetIds(ids); setDemoAssetsFavorite(affected,favorite); return result(affected); },
      async setArchived(ids, archived) { const affected=existingAssetIds(ids); setDemoAssetsArchived(affected,archived); return result(affected); },
      async sync(ids) { const affected=existingAssetIds(ids); syncDemoAssets(affected); return result(affected); },
      async trash(ids) { const affected=existingAssetIds(ids); trashDemoAssets(affected); return result(affected); },
      async restore(ids) { const affected=existingTrashIds(ids); restoreDemoTrashAssets(affected); return result(affected); },
      async addToAlbum(ids, albumId) {
        const affected=existingAssetIds(ids);
        if(!demoAssetState.albums.some((album)=>album.id===albumId))return result([],affected.map((id)=>({id,reason:'Album not found'})));
        addDemoAssetsToAlbum(affected,albumId); return result(affected);
      },
      async removeFromAlbums(ids, albumIds) { const affected=existingAssetIds(ids); removeDemoAssetsFromAlbums(affected,albumIds); return result(affected); },
      async addTags(ids, tagIds) { const affected=existingAssetIds(ids); addDemoTagsToAssets(affected,tagIds); return result(affected); },
      async removeTags(ids, tagIds) { const affected=existingAssetIds(ids); removeDemoTagsFromAssets(affected,tagIds); return result(affected); },
      async stack(ids) {
        const affected=existingAssetIds(ids);
        if(affected.length<2)return result([],affected.map((id)=>({id,reason:'At least two assets are required'})));
        stackDemoAssets(affected); return result(affected);
      },
      async unstack(ids) { const affected=existingAssetIds(ids); removeDemoAssetsFromStacks(affected); return result(affected); },
      async setStackPrimary(assetId) {
        const asset=demoAssetById(assetId);
        if(!asset?.stack)return result([],[{id:assetId,reason:'Asset is not stacked'}]);
        const affected=[...asset.stack.assets]; setDemoStackPrimary(assetId); return result(affected);
      },
      async removeCompleteStack(assetId) {
        const asset=demoAssetById(assetId);
        if(!asset?.stack)return result([],[{id:assetId,reason:'Asset is not stacked'}]);
        const affected=[...asset.stack.assets]; removeDemoCompleteStack(assetId); return result(affected);
      },
    },
    albums: {
      list() { return demoAssetState.albums as AlbumRecord[]; },
      async create(name, description='') { return createDemoAlbum(name,description) as AlbumRecord|undefined; },
      async update(id, patch) { if(!demoAssetState.albums.some((album)=>album.id===id))return result([],[{id,reason:'Album not found'}]); updateDemoAlbum(id,patch); return result([id]); },
      async delete(ids) { const existing=ids.filter((id)=>demoAssetState.albums.some((album)=>album.id===id)); deleteDemoAlbums(existing); return result(existing); },
    },
    tags: {
      list() { return demoAssetState.tags as TagRecord[]; },
      async create(name, color=null, parentPath='') { return createDemoTag(name,color,parentPath) as TagRecord|undefined; },
      async update(id, patch) { if(!demoAssetState.tags.some((tag)=>tag.id===id))return result([],[{id,reason:'Tag not found'}]); updateDemoTag(id,patch); return result([id]); },
      async delete(ids) { const existing=ids.filter((id)=>demoAssetState.tags.some((tag)=>tag.id===id)); deleteDemoTags(existing); return result(existing); },
    },
    media: {
      thumbnail(asset) { return demoAssetPreview(asset); },
      fullSize(asset) { return demoAssetFullSize(asset); },
      difference(selected, reference, options={}) {
        const selectedSeed=seedFor(selected.id),referenceSeed=seedFor(reference.id);
        return demoDifferenceMask((selectedSeed%7)+1,selectedSeed%10,referenceSeed%10,options.hue,options.contrast,options.binary);
      },
    },
  };
}
