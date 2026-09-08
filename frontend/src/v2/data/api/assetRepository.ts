import { renderPixelDifference } from '../mediaDifference';
import {
  assetThumbnailUrl,
  assetVideoPlaybackUrl,
  buildViewerMediaUrls,
  isHeicMimeType,
} from '../../../lib/utils/viewerMedia';
import type {
  AssetRecord,
  AssetDetailRecord,
  AssetRepository,
  AssetSearchCriteria,
  AssetSearchGroup,
  AssetSearchQuery,
  AssetSelectionCapabilities,
  AssetSelectionTarget,
  MediaAsset,
  MediaRepository,
  MutationResult,
  PageResult,
  TrashAssetRecord,
  ViewerNavigationRepository,
} from '../contracts';

export type AssetApiFetcher = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

type ApiAssetSummary = {
  id:string; type:string; original_file_name:string; original_mime_type:string|null;
  width:number|null; height:number|null; duration:number|null; taken_at:string;
  file_modified_at:string; is_favorite:boolean; is_archived:boolean; is_trashed:boolean;
  is_offline:boolean; is_edited:boolean; visibility:string|null; has_metadata:boolean;
  live_photo_video_id:string|null; file_size_bytes:number|null;
  tags:Array<{id:string;name:string;color:string|null}>;
  albums:Array<{id:string;name:string}>;
  stack:{id:string;primary_asset_id:string;asset_count:number;assets:Array<{id:string}>}|null;
  source:{kind:'upload'|'external';library_id:string|null;original_path:string|null};
  restore_path?:string|null;
};
type ApiAssetDetail={
  id:string;owner_id:string|null;library_id:string|null;type:string;original_file_name:string;original_path:string|null;original_mime_type:string|null;
  width:number|null;height:number|null;duration:number|null;taken_at:string;file_modified_at:string;created_at:string|null;updated_at:string|null;
  is_favorite:boolean;is_archived:boolean;is_trashed:boolean;is_offline:boolean;is_edited:boolean;visibility:string|null;live_photo_video_id:string|null;
  exif_info:Record<string,unknown>|null;tags:Array<Record<string,unknown>>;stack:Record<string,unknown>|null;
};
type ApiAssetPage={items:ApiAssetSummary[];total:number;page:number;page_size:number;pages:number};
type ApiSelectionCapabilities={count:number;all_favorite:boolean;all_archived:boolean;has_tags:boolean;has_albums:boolean;has_stack_members:boolean;can_stack:boolean;single_asset_id:string|null;can_set_stack_primary:boolean;can_remove_complete_stack:boolean};
type ApiActionPlan={id:string;applicable_count:number;skipped_count:number;missing_ids:string[]};
type ApiActionResult={applied_ids:string[];failed_ids:string[]};
type ApiSelectionResolution={ids:string[];missing_ids:string[]};
type SearchNode={kind:'condition';field:string;operator:string;value:unknown}|SearchExpression;
type SearchExpression={kind:'group';operator:'and'|'or';negate:boolean;children:SearchNode[]};

class AssetApiError extends Error {
  constructor(public readonly status:number,message:string){super(message);this.name='AssetApiError'}
}

async function requestJson<T>(fetcher:AssetApiFetcher,path:string,init?:RequestInit):Promise<T>{
  const headers=new Headers(init?.headers);if(!headers.has('accept'))headers.set('accept','application/json');
  const response=await fetcher(path,{...init,headers});
  if(!response.ok){const body=await response.json().catch(()=>null) as {detail?:unknown}|null;throw new AssetApiError(response.status,typeof body?.detail==='string'?body.detail:`Asset request failed with HTTP ${response.status}.`)}
  return response.status===204?undefined as T:await response.json() as T;
}

function json(body:unknown,method='POST'):RequestInit{return{method,headers:{'content-type':'application/json'},body:JSON.stringify(body)}}
function pageNumber(query:{page?:number;cursor?:string|null}):number{if(query.page)return query.page;const value=Number.parseInt(query.cursor??'',10);return Number.isSafeInteger(value)&&value>0?value:1}
function normalizedDate(value:string,end=false):string{return value.includes('T')?value:`${value}T${end?'23:59:59.999':'00:00:00'}`}
function splitValues(value:string):string[]{return value.split(',').map((item)=>item.trim()).filter(Boolean)}
function condition(field:string,operator:string,value:unknown):SearchNode{return{kind:'condition',field,operator,value}}

function ruleNode(rule:{field:string;op:string;value:string}):SearchNode|null{
  const raw=rule.value.trim();if(!raw)return null;
  const field={mediaType:'type',takenDate:'taken_at',aspectRatio:'aspect_ratio'}[rule.field]??rule.field;
  if(field==='album'||field==='tag'){
    const values=splitValues(raw);if(!values.length)return null;
    return condition(field,rule.op==='isNot'||rule.op==='notContains'?'not_in_any':'in_any',values);
  }
  if(field==='favorite'||field==='archived'){
    const expected=['true','favorite','archived'].includes(raw.toLowerCase());
    return condition(field,'equals',rule.op==='isNot'?!expected:expected);
  }
  if(field==='taken_at')return condition(field,rule.op==='lt'||rule.op==='lte'?'before':'after',normalizedDate(raw,rule.op==='lt'||rule.op==='lte'));
  const value=field==='type'?raw.toUpperCase():field==='width'||field==='height'?Number.parseInt(raw,10):raw;
  const operator={is:'equals',isNot:'not_equals',contains:'contains',gt:'greater_than',gte:'at_least',lt:'less_than',lte:'at_most'}[rule.op]??'equals';
  if(rule.op==='notContains')return{kind:'group',operator:'and',negate:true,children:[condition(field,'contains',value)]};
  return condition(field,operator,value);
}

function searchGroupNode(group:AssetSearchGroup):SearchExpression{
  const children=group.rules.map(ruleNode).filter((node):node is SearchNode=>Boolean(node));
  children.push(...(group.groups??[]).map(searchGroupNode));
  return{kind:'group',operator:group.logic.toLowerCase() as 'and'|'or',negate:group.negated,children};
}

export function assetSearchExpression(criteria:AssetSearchCriteria):SearchExpression{
  if(criteria.mode==='simple'){
    const f=criteria.filters,children:SearchNode[]=[];
    if(f.filename?.trim())children.push(condition('filename','contains',f.filename.trim()));
    if(f.mediaType)children.push(condition('type','equals',f.mediaType.toUpperCase()));
    if(f.favorite)children.push(condition('favorite','equals',f.favorite==='Favorite'));
    if(f.archived)children.push(condition('archived','equals',f.archived==='Archived'));
    if(f.albumIds?.length)children.push(condition('album','in_any',f.albumIds));
    if(f.tagIds?.length)children.push(condition('tag','in_any',f.tagIds));
    if(f.noAlbum)children.push(condition('album','has_none',[]));
    if(f.noTag)children.push(condition('tag','has_none',[]));
    if(f.takenAfter)children.push(condition('taken_at','after',normalizedDate(f.takenAfter)));
    if(f.takenBefore)children.push(condition('taken_at','before',normalizedDate(f.takenBefore,true)));
    for(const [key,field,operator] of [['minWidth','width','at_least'],['maxWidth','width','at_most'],['minHeight','height','at_least'],['maxHeight','height','at_most'],['minAspectRatio','aspect_ratio','at_least'],['maxAspectRatio','aspect_ratio','at_most']] as const){const value=f[key];if(value)children.push(condition(field,operator,field==='aspect_ratio'?value:Number.parseInt(value,10)))}
    return{kind:'group',operator:'and',negate:false,children};
  }
  const children=criteria.rules.map(ruleNode).filter((node):node is SearchNode=>Boolean(node));
  children.push(...criteria.groups.map(searchGroupNode));
  return{kind:'group',operator:criteria.logic.toLowerCase() as 'and'|'or',negate:criteria.negated,children};
}

function searchBody(query:AssetSearchQuery,page:number){return{expression:assetSearchExpression(query),sort_field:query.sort.field==='filename'?'filename':'taken_at',sort_direction:query.sort.direction,page,page_size:query.pageSize}}
function selectionBody(target:AssetSelectionTarget){return target.kind==='ids'?{mode:'explicit',ids:[...new Set(target.ids)],excluded_ids:[]}:{mode:'all_matching',ids:[],expression:assetSearchExpression(target.criteria),excluded_ids:[...new Set(target.excludedIds)]}}
function normalizeAsset(asset:ApiAssetSummary):AssetRecord{return{id:asset.id,owner_id:null,library_id:asset.source.library_id,asset_type:(['IMAGE','VIDEO','AUDIO'].includes(asset.type)?asset.type:'OTHER') as AssetRecord['asset_type'],original_file_name:asset.original_file_name,original_path:asset.source.original_path,original_mime_type:asset.original_mime_type,checksum:null,file_size_bytes:asset.file_size_bytes,width:asset.width,height:asset.height,duration:asset.duration,file_created_at:asset.taken_at,file_modified_at:asset.file_modified_at,local_date_time:null,immich_created_at:null,immich_updated_at:null,is_favorite:asset.is_favorite,is_archived:asset.is_archived,is_offline:asset.is_offline,is_edited:asset.is_edited,has_metadata:asset.has_metadata,visibility:asset.visibility,live_photo_video_id:asset.live_photo_video_id,tags:asset.tags.map((tag)=>({...tag,value:tag.name})),stack:asset.stack?{id:asset.stack.id,primaryAssetId:asset.stack.primary_asset_id,assetCount:asset.stack.asset_count,assets:asset.stack.assets.map((member)=>member.id)}:null,synced_at:asset.file_modified_at}}
function detailString(value:unknown):string|null{return typeof value==='string'&&value?value:null}
function normalizeDetail(detail:ApiAssetDetail,summary:ApiAssetSummary|null):AssetDetailRecord{
  const tags=detail.tags.map((tag)=>{const id=detailString(tag.id),name=detailString(tag.name)??detailString(tag.value);return id&&name?{id,name,value:detailString(tag.value)??name,color:detailString(tag.color)}:null}).filter((tag):tag is NonNullable<typeof tag>=>Boolean(tag));
  const stackId=detailString(detail.stack?.id),primaryAssetId=detailString(detail.stack?.primaryAssetId),stackAssets=Array.isArray(detail.stack?.assets)?detail.stack.assets:[];
  const memberIds=stackAssets.map((member)=>typeof member==='object'&&member!==null?detailString((member as Record<string,unknown>).id):null).filter((id):id is string=>Boolean(id));
  const exifSize=detail.exif_info?.fileSizeInByte;
  return{id:detail.id,owner_id:detail.owner_id,library_id:detail.library_id,asset_type:(['IMAGE','VIDEO','AUDIO'].includes(detail.type)?detail.type:'OTHER') as AssetRecord['asset_type'],original_file_name:detail.original_file_name,original_path:detail.library_id?detail.original_path:null,original_mime_type:detail.original_mime_type,checksum:null,file_size_bytes:typeof exifSize==='number'&&exifSize>=0?exifSize:summary?.file_size_bytes??null,width:detail.width,height:detail.height,duration:detail.duration,file_created_at:detail.taken_at,file_modified_at:detail.file_modified_at,local_date_time:null,immich_created_at:detail.created_at,immich_updated_at:detail.updated_at,is_favorite:detail.is_favorite,is_archived:detail.is_archived,is_offline:detail.is_offline,is_edited:detail.is_edited,has_metadata:Boolean(detail.exif_info??summary?.has_metadata),visibility:detail.visibility,live_photo_video_id:detail.live_photo_video_id,tags:tags.length?tags:summary?.tags.map((tag)=>({...tag,value:tag.name}))??[],stack:stackId&&primaryAssetId?{id:stackId,primaryAssetId,assetCount:memberIds.length||summary?.stack?.asset_count||1,assets:memberIds.length?memberIds:summary?.stack?.assets.map((member)=>member.id)??[]}:summary?.stack?{id:summary.stack.id,primaryAssetId:summary.stack.primary_asset_id,assetCount:summary.stack.asset_count,assets:summary.stack.assets.map((member)=>member.id)}:null,synced_at:summary?.file_modified_at??detail.file_modified_at,albums:summary?.albums??[]};
}
function normalizeTrash(asset:ApiAssetSummary):TrashAssetRecord{return{id:asset.id,type:(['IMAGE','VIDEO','AUDIO'].includes(asset.type)?asset.type:'OTHER') as TrashAssetRecord['type'],original_file_name:asset.original_file_name,original_mime_type:asset.original_mime_type,width:asset.width,height:asset.height,duration:asset.duration,taken_at:asset.taken_at,file_modified_at:asset.file_modified_at,is_favorite:asset.is_favorite,is_archived:asset.is_archived,restore_path:asset.restore_path??asset.source.original_path}}
function resultFromAction(result:ApiActionResult):MutationResult{return{affectedIds:result.applied_ids,failed:result.failed_ids.map((id)=>({id,reason:'Immich could not apply this action.'}))}}

export function createAssetApiProfile(fetcher:AssetApiFetcher=globalThis.fetch):{assets:AssetRepository;navigation:ViewerNavigationRepository;media:MediaRepository}{
  let lastKey='',lastQuery:AssetSearchQuery|null=null;const pages=new Map<number,AssetRecord[]>();let lastTotal=0;
  let lastTrashQuery:Parameters<AssetRepository['searchTrash']>[0]|null=null;const trashPages=new Map<number,TrashAssetRecord[]>();let lastTrashTotal=0;
  async function fetchAssets(query:AssetSearchQuery,remember=true):Promise<PageResult<AssetRecord>>{const page=pageNumber(query);const response=await requestJson<ApiAssetPage>(fetcher,'/api/assets/search',{...json(searchBody(query,page)),signal:query.signal});const items=response.items.map(normalizeAsset);if(remember){const key=JSON.stringify({...query,page:undefined,cursor:undefined,signal:undefined});if(key!==lastKey){pages.clear();lastKey=key}lastQuery=query;lastTotal=response.total;pages.set(page,items)}return{items,total:response.total,pageSize:response.page_size,page:response.page,nextCursor:response.page<response.pages?String(response.page+1):null}}
  async function resolve(target:AssetSelectionTarget){return requestJson<ApiSelectionResolution>(fetcher,'/api/assets/selection/resolve',json(selectionBody(target)))}
  async function action(target:AssetSelectionTarget,intent:string,relationIds:string[]=[],primary?:string):Promise<MutationResult>{const plan=await requestJson<ApiActionPlan>(fetcher,'/api/assets/actions/plan',json({selection:selectionBody(target),action:intent,relation_ids:relationIds,...(intent==='stack'?{stack_resolution:'move_selected',stack_primary_asset_id:primary}:{} )}));const executed=await requestJson<ApiActionResult>(fetcher,'/api/assets/actions/execute',json({plan_id:plan.id,confirm:true}));return resultFromAction(executed)}
  const assets:AssetRepository={
    async getById(id){try{const item=await requestJson<ApiAssetSummary|null>(fetcher,`/api/assets/${encodeURIComponent(id)}/summary`);return item?normalizeAsset(item):undefined}catch(error){if(error instanceof AssetApiError&&error.status===404)return undefined;throw error}},
    async details(id){try{const encoded=encodeURIComponent(id);const [detail,summary]=await Promise.all([requestJson<ApiAssetDetail>(fetcher,`/api/assets/${encoded}`),requestJson<ApiAssetSummary|null>(fetcher,`/api/assets/${encoded}/summary`).catch((error)=>{if(error instanceof AssetApiError&&error.status===404)return null;throw error})]);return normalizeDetail(detail,summary)}catch(error){if(error instanceof AssetApiError&&error.status===404)return undefined;throw error}},
    async getMany(ids){const unique=[...new Set(ids)],items:AssetRecord[]=[];for(let index=0;index<unique.length;index+=8){const batch=await Promise.all(unique.slice(index,index+8).map((id)=>assets.getById(id)));items.push(...batch.filter((item):item is AssetRecord=>Boolean(item)))}return items},
    async getTrashById(id){try{const item=await requestJson<ApiAssetSummary>(fetcher,`/api/restore/${encodeURIComponent(id)}`);return normalizeTrash(item)}catch(error){if(error instanceof AssetApiError&&error.status===404)return undefined;throw error}},
    search:fetchAssets,
    async searchTrash(query){const page=pageNumber(query),params=new URLSearchParams({page:String(page),page_size:String(query.pageSize)});const response=await requestJson<ApiAssetPage>(fetcher,`/api/restore?${params}`,{signal:query.signal}),items=response.items.map(normalizeTrash);lastTrashQuery=query;lastTrashTotal=response.total;trashPages.set(page,items);return{items,total:response.total,pageSize:response.page_size,page:response.page,nextCursor:response.page<response.pages?String(response.page+1):null}},
    async selectionCapabilities(target,signal){const value=await requestJson<ApiSelectionCapabilities>(fetcher,'/api/assets/selection/capabilities',{...json(selectionBody(target)),signal});return{count:value.count,allFavorite:value.all_favorite,allArchived:value.all_archived,hasTags:value.has_tags,hasAlbums:value.has_albums,hasStackMembers:value.has_stack_members,canStack:value.can_stack,singleAssetId:value.single_asset_id,canSetStackPrimary:value.can_set_stack_primary,canRemoveCompleteStack:value.can_remove_complete_stack}},
    setFavorite:(target)=>action(target,'favorite_toggle'),setArchived:(target)=>action(target,'archive_toggle'),
    async sync(target){const resolution=await resolve(target);await requestJson(fetcher,'/api/assets/sync/selection',json(selectionBody(target)));return{affectedIds:resolution.ids,failed:resolution.missing_ids.map((id)=>({id,reason:'Asset is no longer synchronized.'}))}},
    trash:(target)=>action(target,'trash'),
    async restore(target){if(target.kind==='all'&&target.excludedIds.length)throw new Error('Restore all with exclusions is not available yet.');const body=target.kind==='ids'?{ids:target.ids}:{all:true};await requestJson(fetcher,'/api/restore',json(body));return{affectedIds:target.kind==='ids'?[...target.ids]:[],failed:[]}},
    addToAlbum:(target,albumId)=>action(target,'add_album',[albumId]),removeFromAlbums:(target,albumIds=[])=>action(target,'remove_album',[...albumIds]),
    addTags:(target,tagIds)=>action(target,'add_tag',[...tagIds]),removeTags:(target,tagIds=[])=>action(target,'remove_tag',[...tagIds]),
    async stack(target){const resolution=await resolve(target);const primary=resolution.ids[0];if(!primary)return{affectedIds:[],failed:resolution.missing_ids.map((id)=>({id,reason:'Asset is no longer synchronized.'}))};return action(target,'stack',[],primary)},
    unstack:(target)=>action(target,'remove_from_stack'),setStackPrimary:(id)=>action({kind:'ids',ids:[id]},'set_stack_primary'),removeCompleteStack:(id)=>action({kind:'ids',ids:[id]},'remove_stack'),
  };
  async function adjacent(currentId:string){
    for(const [page,items] of pages){
      const index=items.findIndex((item)=>item.id===currentId);if(index<0)continue;
      let previousId:string|null=items[index-1]?.id??null,nextId:string|null=items[index+1]?.id??null;
      if(!previousId&&page>1&&lastQuery){const prior=await fetchAssets({...lastQuery,page:page-1,cursor:undefined},false);previousId=prior.items.at(-1)?.id??null}
      if(!nextId&&lastQuery&&page*lastQuery.pageSize<lastTotal){const following=await fetchAssets({...lastQuery,page:page+1,cursor:undefined},false);nextId=following.items[0]?.id??null}
      return{previousId,nextId,position:(page-1)*(lastQuery?.pageSize??items.length)+index+1,total:lastTotal};
    }
    return{previousId:null,nextId:null,position:null,total:lastTotal};
  }
  async function adjacentTrash(currentId:string){for(const [page,items] of trashPages){const index=items.findIndex((item)=>item.id===currentId);if(index<0)continue;let previousId:string|null=items[index-1]?.id??null,nextId:string|null=items[index+1]?.id??null;if(!previousId&&page>1&&lastTrashQuery){const prior=await assets.searchTrash({...lastTrashQuery,page:page-1,cursor:undefined});previousId=prior.items.at(-1)?.id??null}if(!nextId&&lastTrashQuery&&page*lastTrashQuery.pageSize<lastTrashTotal){const following=await assets.searchTrash({...lastTrashQuery,page:page+1,cursor:undefined});nextId=following.items[0]?.id??null}return{previousId,nextId,position:(page-1)*(lastTrashQuery?.pageSize??items.length)+index+1,total:lastTrashTotal}}return{previousId:null,nextId:null,position:null,total:lastTrashTotal}}
  const navigation:ViewerNavigationRepository={asset:adjacent,trash:adjacentTrash};
  const media:MediaRepository={thumbnail(asset){return{url:assetThumbnailUrl(asset.id,'thumbnail'),fallbackUrls:[],mimeType:'image/jpeg',posterUrl:null,delivery:'thumbnail',originalMimeType:asset.original_mime_type,expiresAt:null}},view(asset){const video=('asset_type'in asset?asset.asset_type:asset.type)==='VIDEO';if(video)return{url:assetVideoPlaybackUrl(asset.id),fallbackUrls:[],mimeType:'video/mp4',posterUrl:assetThumbnailUrl(asset.id,'preview'),delivery:'transcoded',originalMimeType:asset.original_mime_type,expiresAt:null};const [url,...fallbackUrls]=buildViewerMediaUrls(asset.id,asset.original_mime_type,false),original=Boolean(url?.includes('/original'));return{url:url??assetThumbnailUrl(asset.id,'preview'),fallbackUrls,mimeType:original?asset.original_mime_type:'image/jpeg',posterUrl:null,delivery:isHeicMimeType(asset.original_mime_type)||!original?'decoded':'original',originalMimeType:asset.original_mime_type,expiresAt:null}},async difference(selected,reference,options={}){return renderPixelDifference(media.view(selected),media.view(reference),options)},async refresh(asset,purpose){return purpose==='thumbnail'?media.thumbnail(asset):media.view(asset)}};
  return{assets,navigation,media};
}
