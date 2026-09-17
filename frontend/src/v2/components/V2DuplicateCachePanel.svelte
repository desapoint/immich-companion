<script lang="ts">
  import { onMount } from 'svelte';

  import { jsonRequest, requestJson } from '../../lib/api/http';
  import { formatBytes } from '../../lib/utils/fileSize';
  import type { SimilarityCacheKind, SimilarityCacheStatus } from '../data/contracts';
  import { readDuplicateDiscoveryPreferences } from '../state/duplicateDiscoveryPreferences';
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2ConfirmDialog from './V2ConfirmDialog.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Stack from './V2Stack.svelte';

  type ApiGeneration = {
    epoch: number;
    code_generation: number;
    recorded_descriptor_fingerprint: string;
    current_descriptor_fingerprint: string;
    descriptor_current: boolean;
    rebuilt_at: string|null;
  };
  type ApiRebuildResult = {
    generation: ApiGeneration;
    cancelled_task_count: number;
    removed_counts: Record<string,number>;
    task_id: string;
  };
  type ApiTask = {
    status: string;
    error?: { message?: string }|null;
  };

  const REBUILD_TASK_KEY='immich-companion:v2:similarity-evidence-rebuild-task';
  const REBUILD_MESSAGE_KEY='immich-companion:v2:similarity-evidence-rebuild-message';
  const sleep=(milliseconds:number)=>new Promise((resolve)=>setTimeout(resolve,milliseconds));

  let { status, loading=false, onrefresh, onclear }: {
    status: SimilarityCacheStatus|null;
    loading?: boolean;
    onrefresh:()=>void;
    onclear:(cache:SimilarityCacheKind)=>void;
  }=$props();

  let generation=$state<ApiGeneration|null>(null);
  let generationLoading=$state(false);
  let rebuildOpen=$state(false);
  let rebuilding=$state(false);
  let rebuildMessage=$state('');
  let rebuildError=$state('');

  const ratio=(hits:number,misses:number)=>hits+misses?`${Math.round(hits/(hits+misses)*100)}% hit`:'No requests yet';

  async function loadGeneration():Promise<void>{
    generationLoading=true;
    try{
      generation=await requestJson<ApiGeneration>('/api/v2/duplicates/similarity-evidence/generation');
    }catch{
      generation=null;
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
          onrefresh();
          return;
        }
        await sleep(1500);
      }
    }catch(error){
      rebuildError=error instanceof Error?error.message:'Similarity evidence rebuild status could not be loaded.';
      rebuilding=false;
    }
  }

  async function rebuildEvidence():Promise<void>{
    if(rebuilding)return;
    rebuilding=true;
    rebuildError='';
    rebuildMessage='Invalidating the current evidence generation…';
    try{
      const preferences=readDuplicateDiscoveryPreferences();
      const result=await requestJson<ApiRebuildResult>(
        '/api/v2/duplicates/similarity-evidence/rebuild',
        jsonRequest('POST',{
          similarity_threshold:preferences.similarityThreshold,
          validation_mode:preferences.validationMode,
          anchor_asset_id:null,
          scope:'all_eligible_assets',
          maximum_perceptual_distance:12,
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
      onrefresh();
    }
  }

  onMount(()=>{
    void loadGeneration();
    const completed=sessionStorage.getItem(REBUILD_MESSAGE_KEY);
    if(completed){rebuildMessage=completed;sessionStorage.removeItem(REBUILD_MESSAGE_KEY)}
    const taskId=sessionStorage.getItem(REBUILD_TASK_KEY);
    if(taskId)void monitorRebuild(taskId);
  });
</script>

<V2Card title="Similarity cache">
  <V2Stack gap="md">
    {#if status}
      <V2Inline gap="sm" wrap={true}>
        <V2Badge text={`${status.featureCount.toLocaleString()} durable features`}/>
        <V2Badge text={`Config ${status.configFingerprint.slice(0,8)}`}/>
        {#if status.referenceLatencyP95Ms!==null}<V2Badge text={`Reference p95 ${status.referenceLatencyP95Ms.toLocaleString()} ms`}/>{/if}
      </V2Inline>
      <div class="v2-cache-grid">
        <section>
          <b>Preview LRU</b>
          <span>{formatBytes(status.previews.usedBytes)} / {formatBytes(status.previews.maxBytes)}</span>
          <small>{status.previews.entryCount.toLocaleString()} files · {ratio(status.previews.hits,status.previews.misses)}</small>
          <V2Button disabled={loading||rebuilding||status.previews.entryCount===0} onclick={()=>onclear('previews')}>Clear previews</V2Button>
        </section>
        <section>
          <b>Pair results</b>
          <span>{formatBytes(status.pairEstimatedBytes)} / {formatBytes(status.pairMaxBytes)}</span>
          <small>{status.pairCount.toLocaleString()} pairs · {ratio(status.pairHits,status.pairMisses)}</small>
          <V2Button disabled={loading||rebuilding||status.pairCount===0} onclick={()=>onclear('pairs')}>Clear pair results</V2Button>
        </section>
        <section>
          <b>Hot groups</b>
          <span>{formatBytes(status.hotEstimatedBytes)} / {formatBytes(status.hotMaxBytes)}</span>
          <small>{status.hotCount.toLocaleString()} pairs · {ratio(status.hotHits,status.hotMisses)}</small>
          <V2Button disabled={loading||rebuilding||status.hotCount===0} onclick={()=>onclear('hot')}>Clear memory cache</V2Button>
        </section>
        <section>
          <b>Decode workspace</b>
          <span>{formatBytes(status.decode.usedBytes)} / {formatBytes(status.decode.maxBytes)}</span>
          <small>{status.decode.healthy?'Writable':'Unavailable'} · {status.decode.cleanupFailures.toLocaleString()} cleanup failures</small>
          <V2Button disabled={loading||rebuilding||status.decode.entryCount===0} onclick={()=>onclear('decode')}>Clear abandoned files</V2Button>
        </section>
      </div>
      <small class="v2-muted">Clearing disposable previews or pair results does not remove durable Appearance features, review decisions, or history.</small>

      <div class="v2-evidence-generation">
        <V2Stack gap="sm">
          <V2Inline gap="sm" wrap={true}>
            <b>Similarity evidence generation</b>
            {#if generation}
              <V2Badge text={`Epoch ${generation.epoch}`}/>
              <V2Badge text={`Code generation ${generation.code_generation}`}/>
              {#if !generation.descriptor_current}<V2Badge tone="warn" text="Generation changed"/>{/if}
            {:else if generationLoading}
              <V2Badge text="Loading generation…"/>
            {/if}
          </V2Inline>
          <small class="v2-muted">The epoch is a hard boundary for search fingerprints, detailed validation, pair scores, scans, and the derived duplicate projection. Review decisions and resolution history are preserved.</small>
          {#if generation?.rebuilt_at}<small class="v2-muted">Last rebuilt {new Date(generation.rebuilt_at).toLocaleString()}.</small>{/if}
          {#if rebuildMessage}<small class="v2-rebuild-ok">{rebuildMessage}</small>{/if}
          {#if rebuildError}<small class="v2-rebuild-error">{rebuildError}</small>{/if}
          <V2Button variant="danger" disabled={loading||rebuilding||generationLoading} onclick={()=>rebuildOpen=true}>{rebuilding?'Rebuilding similarity evidence…':'Rebuild similarity evidence'}</V2Button>
        </V2Stack>
      </div>
    {:else}
      <span class="v2-muted">Cache telemetry is unavailable for this data source.</span>
    {/if}
    <V2Button disabled={loading||rebuilding} onclick={onrefresh}>{loading?'Refreshing cache…':'Refresh cache status'}</V2Button>
  </V2Stack>
</V2Card>

{#if rebuildOpen}
  <V2ConfirmDialog
    title="Rebuild similarity evidence?"
    message="This creates a new evidence epoch and invalidates the current similarity results before rebuilding them from the synchronized library."
    confirmLabel="Rebuild similarity evidence"
    destructive={true}
    pending={rebuilding}
    onconfirm={()=>void rebuildEvidence()}
    onclose={()=>rebuildOpen=false}
  >
    {#snippet detail()}
      <V2Stack gap="sm">
        <span>Active similarity scan/index work is cancelled. Search fingerprints, detailed validation, pair scores, completed similarity scans, unavailable markers, and the derived duplicate projection are invalidated.</span>
        <span>Review decisions and resolution history are not deleted. A fresh similarity scan is durably queued in the same server transaction using your saved discovery threshold, validation mode, and candidate limit.</span>
      </V2Stack>
    {/snippet}
  </V2ConfirmDialog>
{/if}

<style>
  .v2-cache-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}
  section{display:flex;flex-direction:column;gap:7px;padding:12px;border:1px solid var(--v2-border,rgba(127,127,127,.22));border-radius:10px;background:var(--v2-surface,Canvas)}
  section small{opacity:.7}
  .v2-evidence-generation{padding-top:4px;border-top:1px solid var(--v2-border,rgba(127,127,127,.22))}
  .v2-rebuild-ok{color:var(--v2-green,#39a96b)}
  .v2-rebuild-error{color:var(--v2-red,#d45b5b)}
</style>
