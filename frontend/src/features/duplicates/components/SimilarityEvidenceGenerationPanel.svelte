<script lang="ts">
  import { onMount } from 'svelte';

  import { jsonRequest, requestJson } from '../../../lib/api/http';
  import { duplicateDiscoverySettingsRepository } from '../api/duplicateDiscoverySettingsRepository';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';
  import V2Inline from '../../../lib/components/layout/Inline.svelte';
  import V2Progress from '../../../lib/components/ui/Progress.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';

  type ApiGeneration = {
    epoch: number;
    code_generation: number;
    recorded_descriptor_fingerprint: string;
    current_descriptor_fingerprint: string;
    descriptor_current: boolean;
    rebuilt_at: string|null;
  };
  type ApiDestroyResult = {
    task_id?: string;
    generation?: ApiGeneration;
    cancelled_task_count: number;
    removed_counts: Record<string,number>;
  };
  type ApiRebuildResult = ApiDestroyResult & {
    generation: ApiGeneration;
    task_id: string;
  };
  type ApiTask = {
    status: string;
    error?: { message?: string }|null;
    progress?: { detail?: string|null; percent?: number|null };
  };

  const DESTROY_TASK_KEY='immich-companion:v2:similarity-evidence-destroy-task';
  const REBUILD_TASK_KEY='immich-companion:v2:similarity-evidence-rebuild-task';
  const REBUILD_MESSAGE_KEY='immich-companion:v2:similarity-evidence-rebuild-message';
  const sleep=(milliseconds:number)=>new Promise((resolve)=>setTimeout(resolve,milliseconds));

  let generation=$state<ApiGeneration|null>(null);
  let generationLoading=$state(false);
  let generationError=$state('');
  let destroyOpen=$state(false);
  let destroying=$state(false);
  let destroyProgress=$state('Destroying the current similarity evidence…');
  let destroyPercent=$state<number|null>(null);
  let rebuildOpen=$state(false);
  let rebuilding=$state(false);
  let rebuildMessage=$state('');
  let rebuildError=$state('');

  async function loadGeneration():Promise<void>{
    generationLoading=true;
    generationError='';
    try{
      generation=await requestJson<ApiGeneration>('/api/v2/duplicates/similarity-evidence/generation');
    }catch(error){
      generation=null;
      generationError=error instanceof Error?error.message:'Similarity evidence generation status could not be loaded.';
    }finally{
      generationLoading=false;
    }
  }

  async function monitorRebuild(taskId:string):Promise<void>{
    rebuilding=true;
    rebuildError='';
    rebuildMessage='Rebuilding similarity evidence…';
    try{
      for(;;){
        const task=await requestJson<ApiTask>(`/api/tasks/${encodeURIComponent(taskId)}`);
        if(task.status==='completed'){
          sessionStorage.removeItem(REBUILD_TASK_KEY);
          sessionStorage.setItem(REBUILD_MESSAGE_KEY,'Similarity evidence rebuild completed.');
          window.location.reload();
          return;
        }
        if(task.status==='failed'||task.status==='cancelled'){
          sessionStorage.removeItem(REBUILD_TASK_KEY);
          rebuildError=task.error?.message??`Similarity evidence rebuild ${task.status}.`;
          rebuilding=false;
          await loadGeneration();
          return;
        }
        await sleep(1500);
      }
    }catch(error){
      rebuildError=error instanceof Error?error.message:'Similarity evidence rebuild status could not be loaded.';
      rebuilding=false;
    }
  }

  async function monitorDestroy(taskId:string):Promise<void>{
    destroying=true;
    rebuildError='';
    try{
      for(;;){
        const task=await requestJson<ApiTask>(`/api/tasks/${encodeURIComponent(taskId)}`);
        destroyProgress=task.progress?.detail??'Destroying the current similarity evidence…';
        destroyPercent=typeof task.progress?.percent==='number'?task.progress.percent:null;
        if(task.status==='completed'){
          sessionStorage.removeItem(DESTROY_TASK_KEY);
          sessionStorage.setItem(REBUILD_MESSAGE_KEY,'Similarity evidence destruction completed.');
          window.location.reload();
          return;
        }
        if(task.status==='failed'||task.status==='cancelled'){
          sessionStorage.removeItem(DESTROY_TASK_KEY);
          rebuildError=task.error?.message??`Similarity evidence destruction ${task.status}.`;
          destroying=false;
          await loadGeneration();
          return;
        }
        await sleep(1500);
      }
    }catch(error){
      rebuildError=error instanceof Error?error.message:'Similarity evidence destruction status could not be loaded.';
      destroying=false;
    }
  }

  async function destroyEvidence():Promise<void>{
    if(rebuilding||destroying)return;
    destroying=true;
    rebuildError='';
    rebuildMessage='Destroying the current similarity evidence…';
    try{
      const result=await requestJson<ApiDestroyResult>(
        '/api/v2/duplicates/similarity-evidence/destroy',
        jsonRequest('POST',{}),
      );
      if(result.task_id){
        destroyPercent=0;
        sessionStorage.setItem(DESTROY_TASK_KEY,result.task_id);
        destroyOpen=false;
        window.location.reload();
        return;
      }
      if(result.generation)generation=result.generation;
      const message=`Evidence epoch ${result.generation?.epoch??'next'} created. Similarity evidence was destroyed; no scan was queued.`;
      sessionStorage.removeItem(REBUILD_TASK_KEY);
      sessionStorage.setItem(REBUILD_MESSAGE_KEY,message);
      destroyOpen=false;
      window.location.reload();
    }catch(error){
      rebuildError=error instanceof Error?error.message:'Similarity evidence could not be destroyed.';
      destroyOpen=false;
      destroying=false;
      await loadGeneration();
    }
  }

  async function rebuildEvidence():Promise<void>{
    if(rebuilding||destroying)return;
    rebuilding=true;
    rebuildError='';
    rebuildMessage='Invalidating the current evidence generation…';
    try{
      const preferences=await duplicateDiscoverySettingsRepository.load();
      const result=await requestJson<ApiRebuildResult>(
        '/api/v2/duplicates/similarity-evidence/rebuild',
        jsonRequest('POST',{
          similarity_threshold:preferences.similarityThreshold,
          validation_mode:preferences.validationMode,
          max_link_depth:preferences.maxLinkDepth,
          anchor_asset_id:null,
          scope:'all_eligible_assets',
          maximum_perceptual_distance:preferences.maximumPerceptualDistance,
          maximum_aspect_difference:0.05,
          maximum_neighbors_per_asset:Math.min(64,Math.max(1,preferences.maxCandidates)),
          maximum_matches:5000,
        }),
      );
      generation=result.generation;
      rebuildMessage=`Evidence epoch ${result.generation.epoch} created. Fresh similarity scan queued…`;
      sessionStorage.setItem(REBUILD_TASK_KEY,result.task_id);
      rebuildOpen=false;
      // Invalidation and durable scan submission commit atomically on the server. Reload
      // immediately so the invalidated projection disappears; the task id survives and
      // is monitored until the replacement scan and publication finish.
      window.location.reload();
    }catch(error){
      rebuildError=error instanceof Error?error.message:'Similarity evidence could not be rebuilt.';
      rebuildOpen=false;
      rebuilding=false;
      await loadGeneration();
    }
  }

  onMount(()=>{
    void loadGeneration();
    const completed=sessionStorage.getItem(REBUILD_MESSAGE_KEY);
    if(completed){rebuildMessage=completed;sessionStorage.removeItem(REBUILD_MESSAGE_KEY)}
    const taskId=sessionStorage.getItem(REBUILD_TASK_KEY);
    if(taskId)void monitorRebuild(taskId);
    const destroyTaskId=sessionStorage.getItem(DESTROY_TASK_KEY);
    if(destroyTaskId)void monitorDestroy(destroyTaskId);
  });
</script>

<V2Card title="Similarity evidence generation">
  <V2Stack gap="sm">
    <V2Inline gap="sm" wrap={true}>
      {#if generation}
        <V2Badge text={`Current epoch ${generation.epoch}`}/>
        <V2Badge text={`Next epoch ${generation.epoch+1}`}/>
        <V2Badge text={`Code generation ${generation.code_generation}`}/>
        {#if !generation.descriptor_current}<V2Badge tone="warn" text="Generation changed"/>{/if}
      {:else if generationLoading}
        <V2Badge text="Loading evidence epoch…"/>
      {:else}
        <V2Badge tone="warn" text="Evidence epoch unavailable"/>
      {/if}
    </V2Inline>
    <small class="v2-muted">The evidence epoch is the hard boundary for search fingerprints, detailed validation, pair scores, completed similarity scans, unavailable markers, and the derived duplicate projection. Review decisions and resolution history are preserved.</small>
    <small class="v2-muted">Destroy only leaves the evidence empty until a later similarity scan. Rebuild uses the same fingerprint pipeline, but queues that scan immediately with the currently saved discovery settings.</small>
    {#if generation?.rebuilt_at}<small class="v2-muted">Last rebuilt {new Date(generation.rebuilt_at).toLocaleString()}.</small>{/if}
    {#if generationError}<small class="v2-rebuild-error">Generation status: {generationError}</small>{/if}
    {#if rebuildMessage}<small class="v2-rebuild-ok">{rebuildMessage}</small>{/if}
    {#if rebuildError}<small class="v2-rebuild-error">{rebuildError}</small>{/if}
    {#if destroying}
      <V2Progress value={destroyPercent??undefined} indeterminate={destroyPercent===null} label="Similarity evidence destruction progress"/>
      <small class="v2-muted" aria-live="polite">{destroyProgress}{#if destroyPercent!==null} · {Math.round(destroyPercent)}%{/if}</small>
    {/if}
    <V2Inline gap="sm" wrap={true}>
      <V2Button variant="danger" disabled={rebuilding||destroying||generationLoading} onclick={()=>destroyOpen=true}>{destroying?'Destroying similarity evidence…':'Destroy evidence only'}</V2Button>
      <V2Button variant="danger" disabled={rebuilding||destroying||generationLoading} onclick={()=>rebuildOpen=true}>{rebuilding?'Rebuilding similarity evidence…':'Start new evidence epoch & rebuild'}</V2Button>
      <V2Button disabled={rebuilding||destroying||generationLoading} onclick={()=>void loadGeneration()}>{generationLoading?'Refreshing epoch…':'Refresh epoch status'}</V2Button>
    </V2Inline>
  </V2Stack>
</V2Card>

{#if destroyOpen}
  <V2ConfirmDialog
    title={generation?`Destroy evidence in epoch ${generation.epoch}?`:'Destroy current similarity evidence?'}
    message={generation?`This advances the evidence epoch from ${generation.epoch} to ${generation.epoch+1} and destroys all current similarity evidence without starting a replacement scan.`:'This creates the next evidence epoch and destroys all current similarity evidence without starting a replacement scan.'}
    confirmLabel="Destroy evidence only"
    destructive={true}
    pending={destroying}
    onconfirm={()=>void destroyEvidence()}
    onclose={()=>destroyOpen=false}
  >
    {#snippet detail()}
      <V2Stack gap="sm">
        <span>Active similarity scan/index work is cancelled. Search fingerprints, detailed validation, pair scores, completed similarity scans, unavailable markers, and the derived duplicate projection are invalidated.</span>
        <span>Review decisions and resolution history are not deleted. No replacement scan is queued; the next manual similarity scan will rebuild the missing fingerprints before candidate indexing.</span>
      </V2Stack>
    {/snippet}
  </V2ConfirmDialog>
{/if}

{#if rebuildOpen}
  <V2ConfirmDialog
    title={generation?`Create evidence epoch ${generation.epoch+1}?`:'Create a new evidence epoch?'}
    message={generation?`This advances the evidence epoch from ${generation.epoch} to ${generation.epoch+1}, invalidates all current similarity evidence, and rebuilds it from the synchronized library.`:'This creates the next evidence epoch, invalidates all current similarity evidence, and rebuilds it from the synchronized library.'}
    confirmLabel="Create new epoch & rebuild"
    destructive={true}
    pending={rebuilding}
    onconfirm={()=>void rebuildEvidence()}
    onclose={()=>rebuildOpen=false}
  >
    {#snippet detail()}
      <V2Stack gap="sm">
        <span>Active similarity scan/index work is cancelled. Search fingerprints, detailed validation, pair scores, completed similarity scans, unavailable markers, and the derived duplicate projection are invalidated.</span>
        <span>Review decisions and resolution history are not deleted. A fresh full-library similarity scan is durably queued in the same server transaction using your saved discovery threshold, dHash distance, validation mode, link depth, and candidate limit.</span>
      </V2Stack>
    {/snippet}
  </V2ConfirmDialog>
{/if}

<style>
  .v2-rebuild-ok{color:var(--v2-green,#39a96b)}
  .v2-rebuild-error{color:var(--v2-red,#d45b5b)}
</style>
