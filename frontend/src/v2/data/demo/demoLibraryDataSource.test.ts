import { afterEach,describe,expect,it,vi } from 'vitest';
import type { AssetSearchRule } from '../contracts';
import { createDemoLibraryDataSource } from './demoLibraryDataSource.svelte';

afterEach(()=>vi.useRealTimers());

describe('demo V2 asset stack search',()=>{
  it('keeps primary, secondary, and unstacked results distinct',async()=>{
    vi.useFakeTimers();
    const source=createDemoLibraryDataSource();
    const initialized=source.initialize();
    await vi.runAllTimersAsync();
    await initialized;

    async function search(rule:AssetSearchRule){
      const pending=source.assets.search({
        mode:'expert',rules:[rule],groups:[],logic:'AND',negated:false,
        sort:{field:'filename',direction:'asc'},pageSize:200,cursor:null,
      });
      await vi.runAllTimersAsync();
      return pending;
    }

    const stacked=await search({field:'stackMembership',op:'is',value:'true'});
    const unstacked=await search({field:'stackMembership',op:'is',value:'false'});
    const primaries=await search({field:'stackRole',op:'is',value:'true'});
    const secondaries=await search({field:'stackRole',op:'is',value:'false'});

    expect(stacked.items.length).toBeGreaterThan(0);
    expect(unstacked.items.length).toBeGreaterThan(0);
    expect(primaries.items.every((asset)=>asset.stack?.primaryAssetId===asset.id)).toBe(true);
    expect(secondaries.items.length).toBeGreaterThan(0);
    expect(secondaries.items.every((asset)=>Boolean(asset.stack)&&asset.stack?.primaryAssetId!==asset.id)).toBe(true);
    expect(primaries.total+secondaries.total).toBe(stacked.total);
  });
});
