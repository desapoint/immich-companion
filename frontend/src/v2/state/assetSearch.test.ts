import { describe,expect,it } from 'vitest';
import { assetExpressionText,assetFieldSelectOptions,assetOperatorOptionsForField,assetRulesInGroups,assetSearchCounts,buildAssetCriteria,cloneAssetGroups,emptyAssetSimple,hydrateAssetGroups,simpleAssetSearchToExpert,type AssetGroup } from './assetSearch';

const groups:AssetGroup[]=[{
  id:2,logic:'OR',negated:false,rules:[{id:3,field:'favorite',op:'is',value:'true'}],groups:[{
    id:4,logic:'AND',negated:true,rules:[{id:5,field:'filename',op:'contains',value:'copy'}],groups:[],
  }],
}];

describe('recursive asset search state',()=>{
  it('formats and counts child groups at every depth',()=>{
    expect(assetExpressionText([{id:1,field:'mediaType',op:'is',value:'Image'}],groups,'AND',false)).toBe('(Media type is Image AND (Favorite is true OR NOT (Filename contains copy)))');
    expect(assetSearchCounts([{id:1,field:'mediaType',op:'is',value:'Image'}],groups)).toEqual({rules:3,groups:2});
    expect(assetRulesInGroups(groups).map((rule)=>rule.id)).toEqual([3,5]);
  });

  it('deep-clones groups instead of sharing nested editor state',()=>{
    const clone=cloneAssetGroups(groups);
    clone[0]!.groups[0]!.rules[0]!.value='changed';
    expect(groups[0]!.groups[0]!.rules[0]!.value).toBe('copy');
  });

  it('hydrates legacy saved groups that have no child groups',()=>{
    let id=10;
    const hydrated=hydrateAssetGroups([{logic:'AND',negated:false,rules:[{field:'tag',op:'is',value:'tag-1'}]} as never],()=>++id,()=>++id);
    expect(hydrated).toMatchObject([{logic:'AND',groups:[],rules:[{value:'tag-1'}]}]);
  });

  it('preserves recursive groups in expert criteria',()=>{
    const criteria=buildAssetCriteria({sort:'filename:asc',mode:'Expert',simple:emptyAssetSimple(),rules:[],groups,logic:'OR',negated:true});
    expect(criteria).toMatchObject({mode:'expert',logic:'OR',negated:true,groups:[{logic:'OR',groups:[{logic:'AND',negated:true,rules:[{value:'copy'}]}]}]});
  });

  it('converts every simple filter into equivalent expert rules',()=>{
    let id=0;
    const converted=simpleAssetSearchToExpert({
      filename:' photo ',mediaType:'Image',favorite:'Not favorite',archived:'Archived',
      advanced:{albumIds:'album-1, album-2',tagIds:'tag-1',noAlbum:true,noTag:true,takenAfter:'2026-01-01',takenBefore:'2026-12-31',minWidth:'1000',maxWidth:'5000',minHeight:'800',maxHeight:'4000',minAspectRatio:'1.2',maxAspectRatio:'1.8'},
    },()=>++id);
    expect(converted).toMatchObject({logic:'AND',negated:false,groups:[]});
    expect(converted.rules.map(({field,op,value})=>({field,op,value}))).toEqual([
      {field:'filename',op:'contains',value:'photo'},
      {field:'mediaType',op:'is',value:'Image'},
      {field:'favorite',op:'is',value:'false'},
      {field:'archived',op:'is',value:'true'},
      {field:'album',op:'is',value:'album-1,album-2'},
      {field:'tag',op:'is',value:'tag-1'},
      {field:'album',op:'hasNone',value:''},
      {field:'tag',op:'hasNone',value:''},
      {field:'takenDate',op:'gte',value:'2026-01-01'},
      {field:'takenDate',op:'lte',value:'2026-12-31'},
      {field:'width',op:'gte',value:'1000'},
      {field:'width',op:'lte',value:'5000'},
      {field:'height',op:'gte',value:'800'},
      {field:'height',op:'lte',value:'4000'},
      {field:'aspectRatio',op:'gte',value:'1.2'},
      {field:'aspectRatio',op:'lte',value:'1.8'},
    ]);
    expect(new Set(converted.rules.map((rule)=>rule.id)).size).toBe(converted.rules.length);
  });

  it('offers has-none only for relationship fields',()=>{
    expect(assetOperatorOptionsForField('tag').map((option)=>option.value)).toContain('hasNone');
    expect(assetOperatorOptionsForField('album').map((option)=>option.value)).toContain('hasNone');
    expect(assetOperatorOptionsForField('filename').map((option)=>option.value)).not.toContain('hasNone');
  });

  it('offers explicit stack membership and stack role fields',()=>{
    expect(assetFieldSelectOptions).toEqual(expect.arrayContaining([
      {value:'stackMembership',label:'Stack membership'},
      {value:'stackRole',label:'Stack role'},
    ]));
    expect(assetOperatorOptionsForField('stackMembership')).toEqual([{value:'is',label:'is'}]);
    expect(assetOperatorOptionsForField('stackRole')).toEqual([{value:'is',label:'is'}]);
  });

  it('preserves stack predicates inside recursive expert groups',()=>{
    const criteria=buildAssetCriteria({
      sort:'takenDate:desc',mode:'Expert',simple:emptyAssetSimple(),rules:[],logic:'AND',negated:false,
      groups:[{id:20,logic:'OR',negated:false,rules:[
        {id:21,field:'stackMembership',op:'is',value:'true'},
        {id:22,field:'stackRole',op:'is',value:'false'},
      ],groups:[]}],
    });
    expect(criteria).toMatchObject({mode:'expert',groups:[{rules:[
      {field:'stackMembership',op:'is',value:'true'},
      {field:'stackRole',op:'is',value:'false'},
    ]}]});
  });
});
