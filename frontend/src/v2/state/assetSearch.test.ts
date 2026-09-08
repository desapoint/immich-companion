import { describe,expect,it } from 'vitest';
import { assetExpressionText,assetRulesInGroups,assetSearchCounts,buildAssetCriteria,cloneAssetGroups,emptyAssetSimple,hydrateAssetGroups,type AssetGroup } from './assetSearch';

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
});
