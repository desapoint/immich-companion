import { describe, expect, it } from 'vitest';

import { AssetMutationController } from './assetMutations.svelte';
import type { MutationResult } from '../data/contracts';

function deferred<T>(){
  let resolve!:(value:T|PromiseLike<T>)=>void;
  let reject!:(reason?:unknown)=>void;
  const promise=new Promise<T>((res,rej)=>{resolve=res;reject=rej});
  return{promise,resolve,reject};
}

const target={kind:'ids' as const,ids:['asset-1']};
const success:MutationResult={affectedIds:['asset-1'],failed:[]};

describe('AssetMutationController',()=>{
  it('uses one applying then refreshing lifecycle with pending feedback',async()=>{
    const execute=deferred<MutationResult>();
    const refresh=deferred<void>();
    const controller=new AssetMutationController(()=>refresh.promise,()=>{});

    const pending=controller.run('Favorite',()=>execute.promise,target);
    expect(controller.busy).toBe(true);
    expect(controller.phase).toBe('applying');
    expect(controller.feedback).toMatchObject({tone:'pending',title:'Favorite in progress',detail:'Applying change…'});

    execute.resolve(success);
    await Promise.resolve();
    await Promise.resolve();
    expect(controller.busy).toBe(true);
    expect(controller.phase).toBe('refreshing');
    expect(controller.feedback).toMatchObject({tone:'pending',title:'Favorite applied',detail:'Refreshing latest asset state…'});

    refresh.resolve();
    await pending;
    expect(controller.feedback?.tone).toBe('ok');
    expect(controller.busy).toBe(false);
    expect(controller.phase).toBe('idle');
  });

  it('keeps the applied result when reconciliation fails',async()=>{
    const controller=new AssetMutationController(async()=>{throw new Error('refresh failed')},()=>{});

    const result=await controller.run('Favorite',async()=>success,target);

    expect(result).toEqual(success);
    expect(controller.feedback?.tone).toBe('ok');
    expect(controller.error).toContain('Favorite was applied');
    expect(controller.busy).toBe(false);
  });

  it('supports a per-action refresh path for single-asset viewer actions',async()=>{
    let defaultRefreshes=0;
    let singleRefreshes=0;
    const controller=new AssetMutationController(async()=>{defaultRefreshes+=1},()=>{});

    await controller.run('Move to trash',async()=>success,target,{
      refresh:async(result)=>{expect(result).toEqual(success);singleRefreshes+=1},
    });

    expect(singleRefreshes).toBe(1);
    expect(defaultRefreshes).toBe(0);
  });
});
