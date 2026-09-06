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
import type { AlbumRecord, AssetRecord, LibraryDataSource, MutationResult, TagRecord } from '../contracts';

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
