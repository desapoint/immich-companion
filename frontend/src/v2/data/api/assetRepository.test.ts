import { describe,expect,it,vi } from 'vitest';
import { assetSearchExpression,createAssetApiProfile,type AssetApiFetcher } from './assetRepository';

const id='11111111-1111-4111-8111-111111111111';
const secondId='22222222-2222-4222-8222-222222222222';
const summary={id,type:'IMAGE',original_file_name:'photo.heic',original_mime_type:'image/heic',width:4032,height:3024,duration:null,taken_at:'2026-08-01T12:00:00Z',file_modified_at:'2026-08-02T12:00:00Z',is_favorite:true,is_archived:false,is_trashed:false,is_offline:false,is_edited:false,visibility:'timeline',has_metadata:true,live_photo_video_id:null,file_size_bytes:42,tags:[{id:'tag-1',name:'Vacation',color:'#fff'}],stack:{id:'stack-1',primary_asset_id:id,asset_count:2,assets:[{id},{id:secondId}]},source:{kind:'external',library_id:'library-1',original_path:'/external/photo.heic'}};
const response=(body:unknown,status=200)=>new Response(status===204?null:JSON.stringify(body),{status,headers:{'content-type':'application/json'}});

describe('live V2 asset repository',()=>{
  it('maps simple search criteria to the structured backend query',async()=>{
    const fetcher=vi.fn<AssetApiFetcher>(async()=>response({items:[summary],total:49,page:2,page_size:24,pages:3}));
    const controller=new AbortController(),profile=createAssetApiProfile(fetcher);
    const result=await profile.assets.search({mode:'simple',filters:{filename:'photo',mediaType:'Image',favorite:'Favorite',albumIds:['album-1'],noTag:true,minWidth:'1000'},sort:{field:'takenDate',direction:'desc'},page:2,pageSize:24,signal:controller.signal});
    expect(fetcher).toHaveBeenCalledWith('/api/assets/search',expect.objectContaining({method:'POST',signal:controller.signal}));
    const body=JSON.parse(String(fetcher.mock.calls[0]?.[1]?.body));
    expect(body).toMatchObject({sort_field:'taken_at',sort_direction:'desc',page:2,page_size:24});
    expect(body.expression.children).toEqual(expect.arrayContaining([
      {kind:'condition',field:'filename',operator:'contains',value:'photo'},
      {kind:'condition',field:'type',operator:'equals',value:'IMAGE'},
      {kind:'condition',field:'album',operator:'in_any',value:['album-1']},
      {kind:'condition',field:'tag',operator:'has_none',value:[]},
      {kind:'condition',field:'width',operator:'at_least',value:1000},
    ]));
    expect(result.nextCursor).toBe('3');
    expect(result.items[0]).toMatchObject({id,asset_type:'IMAGE',library_id:'library-1',original_path:'/external/photo.heic',tags:[{id:'tag-1',name:'Vacation',value:'Vacation'}],stack:{primaryAssetId:id,assetCount:2}});
  });

  it('preserves expert strict comparisons and negated filename matching',()=>{
    expect(assetSearchExpression({mode:'expert',sort:{field:'filename',direction:'asc'},logic:'AND',negated:false,rules:[{field:'width',op:'gt',value:'3000'},{field:'filename',op:'notContains',value:'copy'}],groups:[]})).toMatchObject({children:[
      {kind:'condition',field:'width',operator:'greater_than',value:3000},
      {kind:'group',negate:true,children:[{field:'filename',operator:'contains',value:'copy'}]},
    ]});
  });

  it('uses capabilities and the existing plan-execute action flow',async()=>{
    const calls:string[]=[];
    const fetcher=vi.fn<AssetApiFetcher>(async(input,init)=>{const path=String(input);calls.push(path);if(path.endsWith('/capabilities'))return response({count:2,all_favorite:false,all_archived:true,has_tags:true,has_albums:true,has_stack_members:false,can_stack:true,single_asset_id:null,can_set_stack_primary:false,can_remove_complete_stack:false});if(path.endsWith('/plan')){const body=JSON.parse(String(init?.body));expect(body).toMatchObject({action:'remove_tag',relation_ids:[]});return response({id:'plan-1',applicable_count:2,skipped_count:0,missing_ids:[]})}return response({applied_ids:[id,secondId],failed_ids:[]})});
    const {assets}=createAssetApiProfile(fetcher),target={kind:'ids' as const,ids:[id,secondId]};
    await expect(assets.selectionCapabilities(target)).resolves.toMatchObject({count:2,allArchived:true,hasTags:true,canStack:true});
    await expect(assets.removeTags(target)).resolves.toEqual({affectedIds:[id,secondId],failed:[]});
    expect(calls).toEqual(['/api/assets/selection/capabilities','/api/assets/actions/plan','/api/assets/actions/execute']);
  });

  it('always resolves and sends a stack primary',async()=>{
    const fetcher=vi.fn<AssetApiFetcher>(async(input,init)=>{const path=String(input);if(path.endsWith('/resolve'))return response({ids:[secondId,id],missing_ids:[]});if(path.endsWith('/plan')){expect(JSON.parse(String(init?.body))).toMatchObject({action:'stack',stack_resolution:'move_selected',stack_primary_asset_id:secondId});return response({id:'plan-2',applicable_count:2,skipped_count:0,missing_ids:[]})}return response({applied_ids:[secondId,id],failed_ids:[]})});
    await createAssetApiProfile(fetcher).assets.stack({kind:'ids',ids:[secondId,id]});
  });

  it('exposes companion media proxies for tiles and the viewer',()=>{
    const {media}=createAssetApiProfile(vi.fn());const asset={...summary,asset_type:'IMAGE'} as never;
    expect(media.thumbnail(asset).url).toBe(`/api/assets/${id}/thumbnail?size=thumbnail`);
    expect(media.view(asset)).toMatchObject({
      url:`/api/assets/${id}/thumbnail?size=fullsize`,
      fallbackUrls:[`/api/assets/${id}/thumbnail?size=preview`],
      delivery:'decoded',
    });
  });

  it('uses originals with derivative fallbacks for browser-compatible images',()=>{
    const {media}=createAssetApiProfile(vi.fn());const asset={...summary,asset_type:'IMAGE',original_mime_type:'image/png'} as never;
    expect(media.view(asset)).toMatchObject({
      url:`/api/assets/${id}/original`,
      fallbackUrls:[
        `/api/assets/${id}/thumbnail?size=fullsize`,
        `/api/assets/${id}/thumbnail?size=preview`,
      ],
      delivery:'original',
    });
  });

  it('uses the compatible Immich playback proxy for videos',()=>{
    const {media}=createAssetApiProfile(vi.fn());const asset={...summary,asset_type:'VIDEO',original_mime_type:'video/quicktime'} as never;
    expect(media.view(asset)).toMatchObject({
      url:`/api/assets/${id}/video/playback`,
      fallbackUrls:[],
      posterUrl:`/api/assets/${id}/thumbnail?size=preview`,
      mimeType:'video/mp4',
      delivery:'transcoded',
    });
  });
});
