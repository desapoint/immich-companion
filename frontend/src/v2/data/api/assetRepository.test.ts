import { describe,expect,it,vi } from 'vitest';
import { assetSearchExpression,createAssetApiProfile,type AssetApiFetcher } from './assetRepository';

const id='11111111-1111-4111-8111-111111111111';
const secondId='22222222-2222-4222-8222-222222222222';
const summary={id,type:'IMAGE',original_file_name:'photo.heic',original_mime_type:'image/heic',width:4032,height:3024,duration:null,taken_at:'2026-08-01T12:00:00Z',file_modified_at:'2026-08-02T12:00:00Z',is_favorite:true,is_archived:false,is_trashed:false,is_offline:false,is_edited:false,visibility:'timeline',has_metadata:true,live_photo_video_id:null,file_size_bytes:42,tags:[{id:'tag-1',name:'Vacation',color:'#fff'}],albums:[{id:'album-1',name:'Summer'}],stack:{id:'stack-1',primary_asset_id:id,asset_count:2,assets:[{id},{id:secondId}]},source:{kind:'external',library_id:'library-1',original_path:'/external/photo.heic'}};
const detail={id,owner_id:'owner-1',library_id:'library-1',type:'IMAGE',original_file_name:'renamed.heic',original_path:'/external/renamed.heic',original_mime_type:'image/heic',width:4032,height:3024,duration:null,taken_at:'2026-08-03T12:00:00Z',file_modified_at:'2026-08-04T12:00:00Z',created_at:'2026-08-03T12:00:00Z',updated_at:'2026-08-04T12:00:00Z',is_favorite:false,is_archived:true,is_trashed:true,is_offline:false,is_edited:true,visibility:'timeline',live_photo_video_id:null,exif_info:{fileSizeInByte:8_388_608},people:[],tags:[{id:'tag-live',name:'Live tag',value:'live/tag',color:'#ABCDEF'}],stack:null,immich_url:null};
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

  it('maps stack membership and role without relying on client-side filtering',()=>{
    expect(assetSearchExpression({mode:'expert',sort:{field:'filename',direction:'asc'},logic:'AND',negated:false,rules:[
      {field:'stackMembership',op:'is',value:'true'},
      {field:'stackRole',op:'is',value:'false'},
    ],groups:[]})).toMatchObject({children:[
      {kind:'condition',field:'stack',operator:'equals',value:true},
      {kind:'condition',field:'stack_primary',operator:'equals',value:false},
    ]});
  });

  it('serializes value-free expert relationship filters',()=>{
    expect(assetSearchExpression({mode:'expert',sort:{field:'filename',direction:'asc'},logic:'AND',negated:false,rules:[{field:'album',op:'hasNone',value:''},{field:'tag',op:'hasNone',value:''}],groups:[]})).toMatchObject({children:[
      {kind:'condition',field:'album',operator:'has_none',value:[]},
      {kind:'condition',field:'tag',operator:'has_none',value:[]},
    ]});
  });

  it('combines live Immich details with companion album context',async()=>{
    const fetcher=vi.fn<AssetApiFetcher>(async(input)=>String(input).endsWith('/summary')?response(summary):response(detail));
    const result=await createAssetApiProfile(fetcher).assets.details(id);
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(result).toMatchObject({
      id,owner_id:'owner-1',original_file_name:'renamed.heic',file_size_bytes:8_388_608,is_favorite:false,is_archived:true,
      albums:[{id:'album-1',name:'Summer'}],tags:[{id:'tag-live',name:'Live tag',value:'live/tag',color:'#ABCDEF'}],
    });
  });

  it('maps the API-only restore detail without requiring a local asset summary',async()=>{
    const fetcher=vi.fn<AssetApiFetcher>(async()=>response(detail));
    const result=await createAssetApiProfile(fetcher).assets.getTrashById(id);
    expect(fetcher).toHaveBeenCalledWith(`/api/restore/${id}`,expect.anything());
    expect(result).toEqual({
      id,type:'IMAGE',original_file_name:'renamed.heic',original_mime_type:'image/heic',width:4032,height:3024,duration:null,
      taken_at:'2026-08-03T12:00:00Z',file_modified_at:'2026-08-04T12:00:00Z',is_favorite:false,is_archived:true,
      restore_path:'/external/renamed.heic',file_size_bytes:8_388_608,library_id:'library-1',is_offline:false,
    });
  });

  it('serializes recursive expert groups without flattening them',()=>{
    const expression=assetSearchExpression({mode:'expert',sort:{field:'filename',direction:'asc'},logic:'AND',negated:false,rules:[],groups:[{logic:'OR',negated:false,rules:[{field:'favorite',op:'is',value:'true'}],groups:[{logic:'AND',negated:true,rules:[{field:'filename',op:'contains',value:'copy'}],groups:[]}]}]});
    expect(expression).toEqual({kind:'group',operator:'and',negate:false,children:[{
      kind:'group',operator:'or',negate:false,children:[
        {kind:'condition',field:'favorite',operator:'equals',value:true},
        {kind:'group',operator:'and',negate:true,children:[{kind:'condition',field:'filename',operator:'contains',value:'copy'}]},
      ],
    }]});
  });

  it('uses capabilities and the existing plan-execute action flow',async()=>{
    const calls:string[]=[];
    const fetcher=vi.fn<AssetApiFetcher>(async(input,init)=>{const path=String(input);calls.push(path);if(path.endsWith('/capabilities'))return response({count:2,all_favorite:false,all_archived:true,has_tags:true,has_albums:true,has_stack_members:false,can_stack:true,single_asset_id:null,can_set_stack_primary:false,can_remove_complete_stack:false});if(path.endsWith('/plan')){const body=JSON.parse(String(init?.body));expect(body).toMatchObject({action:'remove_tag',relation_ids:[]});return response({id:'plan-1',applicable_count:2,skipped_count:0,missing_ids:[]})}return response({applied_ids:[id,secondId],failed_ids:[]})});
    const {assets}=createAssetApiProfile(fetcher),target={kind:'ids' as const,ids:[id,secondId]};
    await expect(assets.selectionCapabilities(target)).resolves.toMatchObject({count:2,allArchived:true,hasTags:true,canStack:true});
    await expect(assets.removeTags(target)).resolves.toEqual({affectedIds:[id,secondId],failed:[]});
    expect(calls).toEqual(['/api/assets/selection/capabilities','/api/assets/actions/plan','/api/assets/actions/execute']);
  });

  it('loads removable relationship options for the complete selection',async()=>{
    const fetcher=vi.fn<AssetApiFetcher>(async(_input,init)=>{expect(JSON.parse(String(init?.body))).toEqual({mode:'explicit',ids:[id,secondId],excluded_ids:[]});return response({albums:[{id:'album-1',name:'Summer',selected_asset_count:1}],tags:[{id:'tag-1',name:'Vacation',selected_asset_count:2}]})});
    await expect(createAssetApiProfile(fetcher).assets.removableRelationships({kind:'ids',ids:[id,secondId]})).resolves.toEqual({
      albums:[{value:'album-1',label:'Summer',subtitle:'Linked to 1 selected asset',selectedAssetCount:1}],
      tags:[{value:'tag-1',label:'Vacation',subtitle:'Linked to 2 selected assets',selectedAssetCount:2}],
    });
    expect(fetcher).toHaveBeenCalledWith('/api/assets/selection/relationships',expect.objectContaining({method:'POST'}));
  });

  it('sends chosen relationship ids while preserving empty ids for remove all',async()=>{
    const plans:unknown[]=[];
    const fetcher=vi.fn<AssetApiFetcher>(async(input,init)=>{const path=String(input);if(path.endsWith('/plan')){plans.push(JSON.parse(String(init?.body)));return response({id:`plan-${plans.length}`,applicable_count:1,skipped_count:1,missing_ids:[]})}return response({applied_ids:[id],failed_ids:[]})});
    const assets=createAssetApiProfile(fetcher).assets,target={kind:'ids' as const,ids:[id,secondId]};
    await assets.removeTags(target,['tag-1','tag-2']);
    await assets.removeFromAlbums(target);
    expect(plans).toEqual([
      expect.objectContaining({action:'remove_tag',relation_ids:['tag-1','tag-2']}),
      expect.objectContaining({action:'remove_album',relation_ids:[]}),
    ]);
  });

  it('always resolves and sends a stack primary',async()=>{
    const fetcher=vi.fn<AssetApiFetcher>(async(input,init)=>{const path=String(input);if(path.endsWith('/resolve'))return response({ids:[secondId,id],missing_ids:[]});if(path.endsWith('/plan')){expect(JSON.parse(String(init?.body))).toMatchObject({action:'stack',stack_resolution:'move_selected',stack_primary_asset_id:secondId});return response({id:'plan-2',applicable_count:2,skipped_count:0,missing_ids:[]})}return response({applied_ids:[secondId,id],failed_ids:[]})});
    await createAssetApiProfile(fetcher).assets.stack({kind:'ids',ids:[secondId,id]});
  });

  it('exposes stack conflicts for review and sends the chosen resolution',async()=>{
    const plans:unknown[]=[];
    const fetcher=vi.fn<AssetApiFetcher>(async(input,init)=>{const path=String(input);if(path.endsWith('/plan')){const body=JSON.parse(String(init?.body));plans.push(body);return response({id:`plan-${plans.length}`,target_count:2,applicable_count:2,skipped_count:0,missing_ids:[],stack_primary_asset_id:id,stack_conflicts:plans.length===1?[{stack_id:'stack-1',selected_count:1,member_count:3,includes_unselected:true}]:[]})}return response({applied_ids:[id,secondId],affected_ids:[id,secondId,'33333333-3333-4333-8333-333333333333'],failed_ids:[]})});
    const assets=createAssetApiProfile(fetcher).assets,target={kind:'ids' as const,ids:[id,secondId]};
    await expect(assets.planStack(target,id)).resolves.toEqual({id:'plan-1',targetCount:2,primaryAssetId:id,conflicts:[{stackId:'stack-1',selectedCount:1,memberCount:3,includesUnselected:true}]});
    const reviewed=await assets.planStack(target,id,'include_existing');
    await expect(assets.executeStack(reviewed.id)).resolves.toEqual({affectedIds:[id,secondId,'33333333-3333-4333-8333-333333333333'],failed:[]});
    expect(plans).toEqual([
      expect.objectContaining({action:'stack',stack_primary_asset_id:id}),
      expect.objectContaining({action:'stack',stack_primary_asset_id:id,stack_resolution:'include_existing'}),
    ]);
    expect(plans[0]).not.toHaveProperty('stack_resolution');
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
