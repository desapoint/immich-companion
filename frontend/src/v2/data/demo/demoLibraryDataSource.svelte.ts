import {
  addDemoAssetsToAlbum, addDemoTagsToAssets, createDemoAlbum, createDemoTag, deleteDemoAlbums, deleteDemoTags,
  demoAssetById, demoAssetState, indexedDemoAssets, initializeDemoAssetState, removeDemoAssetsFromAlbums,
  removeDemoAssetsFromStacks, removeDemoCompleteStack, removeDemoTagsFromAssets, restoreDemoTrashAssets,
  setDemoAssetsArchived, setDemoAssetsFavorite, setDemoStackPrimary, stackDemoAssets, syncDemoAssets,
  trashApiDemoAssets, trashDemoAssets, updateDemoAlbum, updateDemoTag,
} from '../../demo/demoAssetState.svelte';
import { normalizeDemoStacks } from '../../demo/demoAssetConsistency';
import { demoAssetFullSize, demoAssetPreview } from '../../demo/demoAssetVisuals';
import { demoDifferenceMask } from '../../demo/duplicateVisuals';
import type {
  AlbumRecord, AlbumSearchQuery, AssetRecord, AssetSearchCriteria, AssetSearchGroup, AssetSearchQuery, AssetSearchRule,
  LibraryDataSource, MutationResult, PageResult, TagHierarchyRow, TagRecord, TagSearchQuery, TrashAssetRecord, TrashSearchQuery,
} from '../contracts';

const result=(ids:readonly string[],failed:MutationResult['failed']=[]):MutationResult=>({affectedIds:[...new Set(ids)],failed});
const page=<T>(items:T[],total:number,query:{page:number;pageSize:number}):PageResult<T>=>({items,total,page:query.page,pageSize:query.pageSize});
const slicePage=<T>(items:T[],query:{page:number;pageSize:number})=>items.slice(Math.max(0,(query.page-1)*query.pageSize),Math.max(0,(query.page-1)*query.pageSize)+query.pageSize);
const existingAssetIds=(ids:readonly string[])=>{const valid=new Set(demoAssetState.assets.map((asset)=>asset.id));return [...new Set(ids)].filter((id)=>valid.has(id));};
const existingTrashIds=(ids:readonly string[])=>{const valid=new Set(demoAssetState.trash_api_items.map((asset)=>asset.id));return [...new Set(ids)].filter((id)=>valid.has(id));};
function seedFor(id:string){let hash=0;for(let index=0;index<id.length;index+=1)hash=(Math.imul(hash,31)+id.charCodeAt(index))|0;return Math.abs(hash)}
function parseRatio(value:string|undefined){const trimmed=value?.trim();if(!trimmed)return undefined;if(trimmed.includes(':')){const[a,b]=trimmed.split(':').map(Number);return Number.isFinite(a)&&Number.isFinite(b)&&b!==0?a/b:undefined}const number=Number(trimmed);return Number.isFinite(number)?number:undefined}
const albumIdsFor=(assetId:string)=>demoAssetState.album_assets.filter((m)=>m.asset_id===assetId).map((m)=>m.album_id);
const tagIdsFor=(assetId:string)=>demoAssetState.tag_assets.filter((m)=>m.asset_id===assetId).map((m)=>m.tag_id);
function matchesSimple(asset:AssetRecord,query:Extract<AssetSearchCriteria,{mode:'simple'}>){const f=query.filters;if(f.filename&&!asset.original_file_name.toLowerCase().includes(f.filename.toLowerCase()))return false;if(f.mediaType&&asset.asset_type!==(f.mediaType==='Video'?'VIDEO':'IMAGE'))return false;if(f.favorite==='Favorite'&&!asset.is_favorite)return false;if(f.favorite==='Not favorite'&&asset.is_favorite)return false;if(f.archived==='Archived'&&!asset.is_archived)return false;if(f.archived==='Not archived'&&asset.is_archived)return false;const aa=albumIdsFor(asset.id),at=tagIdsFor(asset.id);if(f.albumIds?.length&&!f.albumIds.some((id)=>aa.includes(id)))return false;if(f.noAlbum&&aa.length)return false;if(f.tagIds?.length&&!f.tagIds.some((id)=>at.includes(id)))return false;if(f.noTag&&at.length)return false;const date=asset.file_created_at.slice(0,10);if(f.takenAfter&&date<f.takenAfter)return false;if(f.takenBefore&&date>f.takenBefore)return false;if(f.minWidth&&Number(asset.width??0)<Number(f.minWidth))return false;if(f.maxWidth&&Number(asset.width??0)>Number(f.maxWidth))return false;if(f.minHeight&&Number(asset.height??0)<Number(f.minHeight))return false;if(f.maxHeight&&Number(asset.height??0)>Number(f.maxHeight))return false;const ratio=asset.width&&asset.height?asset.width/asset.height:0,min=parseRatio(f.minAspectRatio),max=parseRatio(f.maxAspectRatio);if(min!==undefined&&ratio<min)return false;if(max!==undefined&&ratio>max)return false;return true}
function comparable(asset:AssetRecord,field:string):string|number|boolean{if(field==='filename')return asset.original_file_name;if(field==='mediaType')return asset.asset_type==='VIDEO'?'Video':'Image';if(field==='favorite')return asset.is_favorite;if(field==='archived')return asset.is_archived;if(field==='album')return albumIdsFor(asset.id).map((id)=>demoAssetState.albums.find((a)=>a.id===id)?.album_name??'').join(' | ');if(field==='tag')return asset.tags.map((tag)=>tag.name).join(' | ');if(field==='takenDate')return asset.file_created_at.slice(0,10);if(field==='width')return asset.width??0;if(field==='height')return asset.height??0;if(field==='aspectRatio')return asset.width&&asset.height?asset.width/asset.height:0;return ''}
function evaluateRule(asset:AssetRecord,rule:AssetSearchRule){const actual=comparable(asset,rule.field),expected=rule.value.trim();if(typeof actual==='boolean'){const truth=['true','favorite','archived'].includes(expected.toLowerCase());return rule.op==='isNot'?actual!==truth:actual===truth}if(typeof actual==='number'){const target=parseRatio(expected)??Number(expected);if(!Number.isFinite(target))return false;if(rule.op==='gt')return actual>target;if(rule.op==='gte')return actual>=target;if(rule.op==='lt')return actual<target;if(rule.op==='lte')return actual<=target;if(rule.op==='isNot')return actual!==target;return actual===target}const left=actual.toLowerCase(),right=expected.toLowerCase();if(rule.op==='contains')return left.includes(right);if(rule.op==='notContains')return!left.includes(right);if(rule.op==='isNot')return left!==right;return left.includes(right)}
function evaluateGroup(asset:AssetRecord,rules:AssetSearchRule[],logic:'AND'|'OR',negated=false){const matched=rules.length===0?true:logic==='AND'?rules.every((r)=>evaluateRule(asset,r)):rules.some((r)=>evaluateRule(asset,r));return negated?!matched:matched}
function matchesExpert(asset:AssetRecord,query:Extract<AssetSearchCriteria,{mode:'expert'}>){const parts=[evaluateGroup(asset,query.rules,query.logic),...query.groups.map((g:AssetSearchGroup)=>evaluateGroup(asset,g.rules,g.logic,g.negated))],matched=query.logic==='AND'?parts.every(Boolean):parts.some(Boolean);return query.negated?!matched:matched}
function searchAssets(criteria:AssetSearchCriteria){const source=(indexedDemoAssets() as AssetRecord[]).filter((asset)=>criteria.mode==='simple'?matchesSimple(asset,criteria):matchesExpert(asset,criteria));const mul=criteria.sort.direction==='desc'?-1:1;return [...source].sort((a,b)=>criteria.sort.field==='filename'?a.original_file_name.localeCompare(b.original_file_name)*mul:a.file_created_at.localeCompare(b.file_created_at)*mul)}
function searchTrash(query:TrashSearchQuery){const mul=query.sort.direction==='desc'?-1:1;return [...trashApiDemoAssets()].sort((a,b)=>{if(query.sort.field==='name')return a.original_file_name.localeCompare(b.original_file_name)*mul;if(query.sort.field==='takenAt')return a.taken_at.localeCompare(b.taken_at)*mul;return a.file_modified_at.localeCompare(b.file_modified_at)*mul})}
function hierarchyRows():TagHierarchyRow[]{const leaves:TagHierarchyRow[]=demoAssetState.tags.map((tag)=>{const parts=tag.tag_name.split(' / ');return{id:tag.id,name:parts.at(-1)??tag.tag_name,path:tag.tag_name,parent:parts.length>1?parts.slice(0,-1).join(' / '):'',assets:tag.asset_count,children:0,color:tag.color,synthetic:false,realTagIds:[tag.id]}});const byPath=new Map(leaves.map((row)=>[row.path,row]));for(const leaf of leaves){const parts=leaf.path.split(' / ');for(let depth=1;depth<parts.length;depth+=1){const path=parts.slice(0,depth).join(' / ');if(byPath.has(path))continue;byPath.set(path,{id:`hierarchy:${path}`,name:parts[depth-1],path,parent:depth>1?parts.slice(0,depth-1).join(' / '):'',assets:0,children:0,color:leaf.color,synthetic:true,realTagIds:[]})}}const rows=[...byPath.values()];for(const row of rows){row.children=rows.filter((candidate)=>candidate.parent===row.path).length;if(row.synthetic){row.realTagIds=demoAssetState.tags.filter((tag)=>tag.tag_name.startsWith(`${row.path} / `)).map((tag)=>tag.id);const ids=new Set(demoAssetState.tag_assets.filter((m)=>row.realTagIds.includes(m.tag_id)).map((m)=>m.asset_id));row.assets=ids.size}}return rows}
function searchTags(query:TagSearchQuery){const normalized=(query.query??'').trim().toLowerCase();const mul=query.sort.direction==='desc'?-1:1;return hierarchyRows().filter((row)=>!normalized||(query.includeHierarchy?row.name.toLowerCase().includes(normalized)||row.path.toLowerCase().includes(normalized):row.name.toLowerCase().includes(normalized))).sort((a,b)=>{if(query.sort.field==='assets')return(a.assets-b.assets)*mul;if(query.sort.field==='children')return(a.children-b.children)*mul;if(query.sort.field==='path')return a.path.localeCompare(b.path)*mul;return a.name.localeCompare(b.name)*mul})}
function searchAlbums(query:AlbumSearchQuery){const normalized=(query.query??'').trim().toLowerCase(),mul=query.sort.direction==='desc'?-1:1;return [...demoAssetState.albums].filter((album)=>!normalized||`${album.album_name}\n${album.description}`.toLowerCase().includes(normalized)).sort((a,b)=>{if(query.sort.field==='assets')return(a.asset_count-b.asset_count)*mul;if(query.sort.field==='description')return a.description.localeCompare(b.description)*mul;return a.album_name.localeCompare(b.album_name)*mul})}

export function createDemoLibraryDataSource():LibraryDataSource{return{
  kind:'demo',
  async initialize(){initializeDemoAssetState();normalizeDemoStacks()},
  assets:{
    async getById(id){return demoAssetById(id) as AssetRecord|undefined},
    async getMany(ids){const set=new Set(ids);return (indexedDemoAssets() as AssetRecord[]).filter((asset)=>set.has(asset.id))},
    async search(query:AssetSearchQuery){const all=searchAssets(query);return page(slicePage(all,query),all.length,query)},
    async searchIds(criteria){return searchAssets(criteria).map((asset)=>asset.id)},
    async searchTrash(query){const all=searchTrash(query);return page(slicePage(all,query),all.length,query)},
    async searchTrashIds(){return trashApiDemoAssets().map((asset)=>asset.id)},
    async relationshipPresence(ids){return ids.map((assetId)=>({assetId,hasTags:demoAssetState.tag_assets.some((m)=>m.asset_id===assetId),hasAlbums:demoAssetState.album_assets.some((m)=>m.asset_id===assetId)}))},
    async setFavorite(ids,favorite){const affected=existingAssetIds(ids);setDemoAssetsFavorite(affected,favorite);return result(affected)},
    async setArchived(ids,archived){const affected=existingAssetIds(ids);setDemoAssetsArchived(affected,archived);return result(affected)},
    async sync(ids){const affected=existingAssetIds(ids);syncDemoAssets(affected);return result(affected)},
    async trash(ids){const affected=existingAssetIds(ids);trashDemoAssets(affected);normalizeDemoStacks();return result(affected)},
    async restore(ids){const affected=existingTrashIds(ids);restoreDemoTrashAssets(affected);normalizeDemoStacks();return result(affected)},
    async addToAlbum(ids,albumId){const affected=existingAssetIds(ids);if(!demoAssetState.albums.some((album)=>album.id===albumId))return result([],affected.map((id)=>({id,reason:'Album not found'})));addDemoAssetsToAlbum(affected,albumId);return result(affected)},
    async removeFromAlbums(ids,albumIds){const affected=existingAssetIds(ids);removeDemoAssetsFromAlbums(affected,albumIds);return result(affected)},
    async addTags(ids,tagIds){const affected=existingAssetIds(ids);addDemoTagsToAssets(affected,tagIds);return result(affected)},
    async removeTags(ids,tagIds){const affected=existingAssetIds(ids);removeDemoTagsFromAssets(affected,tagIds);return result(affected)},
    async stack(ids){const affected=existingAssetIds(ids);if(affected.length<2)return result([],affected.map((id)=>({id,reason:'At least two assets are required'})));stackDemoAssets(affected);normalizeDemoStacks();return result(affected)},
    async unstack(ids){const affected=existingAssetIds(ids);removeDemoAssetsFromStacks(affected);normalizeDemoStacks();return result(affected)},
    async setStackPrimary(assetId){const asset=demoAssetById(assetId);if(!asset?.stack)return result([],[{id:assetId,reason:'Asset is not stacked'}]);const affected=[...asset.stack.assets];setDemoStackPrimary(assetId);return result(affected)},
    async removeCompleteStack(assetId){const asset=demoAssetById(assetId);if(!asset?.stack)return result([],[{id:assetId,reason:'Asset is not stacked'}]);const affected=[...asset.stack.assets];removeDemoCompleteStack(assetId);normalizeDemoStacks();return result(affected)},
  },
  albums:{
    async search(query){const all=searchAlbums(query);return page(slicePage(all,query),all.length,query)},
    async getById(id){return demoAssetState.albums.find((album)=>album.id===id) as AlbumRecord|undefined},
    async create(name,description=''){return createDemoAlbum(name,description) as AlbumRecord|undefined},
    async update(id,patch){if(!demoAssetState.albums.some((album)=>album.id===id))return result([],[{id,reason:'Album not found'}]);updateDemoAlbum(id,patch);return result([id])},
    async delete(ids){const existing=ids.filter((id)=>demoAssetState.albums.some((album)=>album.id===id));deleteDemoAlbums(existing);return result(existing)},
  },
  tags:{
    async search(query){const all=searchTags(query);return page(slicePage(all,query),all.length,query)},
    async getById(id){return demoAssetState.tags.find((tag)=>tag.id===id) as TagRecord|undefined},
    async parentOptions(excludeTagId){const editing=excludeTagId?demoAssetState.tags.find((tag)=>tag.id===excludeTagId)?.tag_name??'':'';return hierarchyRows().filter((row)=>row.children>0&&row.path!==editing&&!row.path.startsWith(`${editing} / `)).map((row)=>({value:row.path,label:row.name,subtitle:row.parent||'Root'}))},
    async create(name,color=null,parentPath=''){return createDemoTag(name,color,parentPath) as TagRecord|undefined},
    async update(id,patch){if(!demoAssetState.tags.some((tag)=>tag.id===id))return result([],[{id,reason:'Tag not found'}]);updateDemoTag(id,patch);return result([id])},
    async delete(ids){const existing=ids.filter((id)=>demoAssetState.tags.some((tag)=>tag.id===id));deleteDemoTags(existing);return result(existing)},
  },
  media:{thumbnail(asset){return demoAssetPreview(asset)},fullSize(asset){return demoAssetFullSize(asset)},difference(selected,reference,options={}){const a=seedFor(selected.id),b=seedFor(reference.id);return demoDifferenceMask((a%7)+1,a%10,b%10,options.hue,options.contrast,options.binary)}},
}}
