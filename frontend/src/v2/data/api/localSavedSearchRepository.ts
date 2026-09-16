import type { AssetSearchCriteria, PageResult, SavedSearchRecord, SavedSearchRepository, SavedSearchQuery } from '../contracts';

const STORAGE_KEY='immichCompanionV2SavedSearches.v1';
type StorageLike=Pick<Storage,'getItem'|'setItem'>;
function cloneCriteria(value:AssetSearchCriteria):AssetSearchCriteria{return structuredClone(value)}
function page(items:SavedSearchRecord[],query:SavedSearchQuery):PageResult<SavedSearchRecord>{const pageSize=Math.max(1,query.pageSize),offset=query.page!==undefined?Math.max(0,(query.page-1)*pageSize):Math.max(0,Number(query.cursor??0)||0),slice=items.slice(offset,offset+pageSize);return{items:slice,total:items.length,pageSize,page:query.page,nextCursor:offset+slice.length<items.length?String(offset+slice.length):null}}

export function createLocalSavedSearchRepository(storage:StorageLike|undefined=typeof localStorage==='undefined'?undefined:localStorage):SavedSearchRepository{
  let records:SavedSearchRecord[]|null=null;
  function load(){if(records)return records;try{const parsed=JSON.parse(storage?.getItem(STORAGE_KEY)??'[]') as SavedSearchRecord[];records=Array.isArray(parsed)?parsed:[]}catch{records=[]}return records}
  function persist(){storage?.setItem(STORAGE_KEY,JSON.stringify(load()))}
  return{
    async getById(id){const record=load().find((item)=>item.id===id);return record?{...record,criteria:cloneCriteria(record.criteria)}:undefined},
    async search(query){const term=(query.query??'').trim().toLowerCase(),sort=query.sort??{field:'updatedAt',direction:'desc'},multiplier=sort.direction==='desc'?-1:1;return page(load().filter((item)=>!term||`${item.name}\n${item.description}`.toLowerCase().includes(term)).sort((a,b)=>(sort.field==='name'?a.name.localeCompare(b.name):a.updatedAt.localeCompare(b.updatedAt))*multiplier).map((item)=>({...item,criteria:cloneCriteria(item.criteria)})),query)},
    async create(input){const name=input.name.trim();if(!name)throw new Error('Saved search name is required.');const now=new Date().toISOString(),id=globalThis.crypto?.randomUUID?.()??`saved-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,8)}`,record:SavedSearchRecord={id,name,description:input.description?.trim()??'',criteria:cloneCriteria(input.criteria),createdAt:now,updatedAt:now};load().unshift(record);persist();return{...record,criteria:cloneCriteria(record.criteria)}},
    async update(id,patch){const index=load().findIndex((item)=>item.id===id);if(index<0)return{affectedIds:[],failed:[{id,reason:'Saved search not found'}]};const current=load()[index],name=patch.name===undefined?current.name:patch.name.trim();if(!name)return{affectedIds:[],failed:[{id,reason:'Saved search name is required'}]};load()[index]={...current,name,description:patch.description===undefined?current.description:patch.description.trim(),criteria:patch.criteria?cloneCriteria(patch.criteria):current.criteria,updatedAt:new Date().toISOString()};persist();return{affectedIds:[id],failed:[]}},
    async delete(ids){const requested=new Set(ids),affected=load().filter((item)=>requested.has(item.id)).map((item)=>item.id);records=load().filter((item)=>!requested.has(item.id));persist();return{affectedIds:affected,failed:ids.filter((id)=>!affected.includes(id)).map((id)=>({id,reason:'Saved search not found'}))}},
  };
}
