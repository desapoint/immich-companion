<script lang="ts">
  import { onMount } from 'svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import V2CronField from '../../../lib/components/ui/CronField.svelte';
  import V2Progress from '../../../lib/components/ui/Progress.svelte';
  import V2SelectField from '../../../lib/components/ui/SimpleSelectField.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';

  type Settings = {model_repo:string;idle_seconds:number;confidence_threshold:number;character_threshold:number;batch_size:number;processed_tag_name:string;content_rating_tag_name:string;target_albums:string;max_batches_per_run:number;unload_model_after_run:boolean;failure_timeout:number;tag_cache_ttl:number;log_level:string;models:string[]};
  type Schedule = {name:string;enabled:boolean;cron_expression:string|null;last_run_at:string|null};
  type Run = {id:string;created_at:string;undone_at:string|null;failures:number};
  type Failure = {asset_id:string;error:string;attempts:number;next_retry_at:string};
  type ModelStatus = {repo:string;revision:string;cached:boolean;loaded:boolean};
  type Task = {id:string;status:string;payload:Record<string,unknown>;progress:Record<string,unknown>|null;counters:Record<string,number>|null;error:{message:string}|null};
  let settings=$state<Settings|null>(null),schedule=$state<Schedule|null>(null),runs=$state<Run[]>([]),models=$state<ModelStatus[]>([]),tasks=$state<Task[]>([]),failures=$state<Failure[]>([]),openRun=$state(''),busy=$state(false),error=$state(''),message=$state('');
  const modelOptions=[
    {value:'SmilingWolf/wd-swinv2-tagger-v3',label:'SwinV2 v3 · same as existing tagger'},
    {value:'SmilingWolf/wd-convnext-tagger-v3',label:'ConvNeXt v3 · smaller model'},
    {value:'SmilingWolf/wd-vit-tagger-v3',label:'ViT v3 · smaller model'},
  ];
  let currentModel=$derived(models.find((item)=>item.repo===settings?.model_repo));
  let currentDownload=$derived(tasks.find((item)=>item.payload.mode==='download'&&item.payload.model_repo===settings?.model_repo));
  let downloadActive=$derived(Boolean(currentDownload&&['queued','running','retrying','recovering','pause_requested','paused','cancel_requested'].includes(currentDownload.status)));
  let downloadPercent=$derived(typeof currentDownload?.progress?.percent==='number'?currentDownload.progress.percent:null);
  let downloadDetail=$derived(typeof currentDownload?.progress?.detail==='string'?currentDownload.progress.detail:'Preparing model files…');
  async function api<T>(path:string,init?:RequestInit):Promise<T>{const response=await fetch(path,init);if(!response.ok){const body=await response.json().catch(()=>null) as {detail?:string}|null;throw new Error(body?.detail??`Request failed (${response.status})`)}return response.json() as Promise<T>}
  function json(value:unknown):RequestInit{return{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(value)}}
  async function refresh(){const [history,cached,recent]=await Promise.all([api<Run[]>('/api/booru/runs'),api<ModelStatus[]>('/api/booru/models/status'),api<Task[]>('/api/tasks?task_type=booru_tagging&limit=30')]);runs=history;models=cached;tasks=recent;if(openRun)failures=await api<Failure[]>(`/api/booru/runs/${openRun}/failures`)}
  async function load(){try{const [next,schedules]=await Promise.all([api<Settings>('/api/booru/settings'),api<Schedule[]>('/api/settings/sync')]);settings=next;schedule=schedules.find((item)=>item.name==='booru-tagging')??null;await refresh()}catch(value){error=value instanceof Error?value.message:'Booru settings could not be loaded.'}}
  async function save(){if(!settings||!schedule||busy)return;busy=true;error='';message='';try{await api('/api/booru/settings',json(settings));schedule=await api<Schedule>(`/api/settings/sync/${schedule.name}`,json({enabled:schedule.enabled,cron_expression:schedule.cron_expression}));message='Booru settings saved.'}catch(value){error=value instanceof Error?value.message:'Booru settings could not be saved.'}finally{busy=false}}
  async function download(){if(busy||!settings)return;busy=true;error='';message='';try{await api('/api/booru/settings',json(settings));await api<{task_id:string}>('/api/booru/models/download',{method:'POST'});message='Model download queued.';await refresh()}catch(value){error=value instanceof Error?value.message:'Model download could not be started.'}finally{busy=false}}
  async function undo(run:Run){if(busy)return;busy=true;error='';message='';try{const result=await api<{assets:number;tags:number}>(`/api/booru/runs/${run.id}/undo`,{method:'POST'});message=`Removed ${result.tags} Booru tags from ${result.assets} assets.`;await refresh()}catch(value){error=value instanceof Error?value.message:'Undo failed. Retry this run.'}finally{busy=false}}
  async function retry(run:Run){if(busy)return;busy=true;error='';message='';try{const result=await api<{selected_count:number}>(`/api/booru/runs/${run.id}/retry`,{method:'POST'});message=`Retry queued for ${result.selected_count} failed images.`;await refresh()}catch(value){error=value instanceof Error?value.message:'Retry could not be queued.'}finally{busy=false}}
  async function toggleFailures(run:Run){if(openRun===run.id){openRun='';failures=[];return}openRun=run.id;try{failures=await api<Failure[]>(`/api/booru/runs/${run.id}/failures`)}catch(value){error=value instanceof Error?value.message:'Failures could not be loaded.'}}
  onMount(()=>{void load();const timer=setInterval(()=>{void refresh().catch(()=>{})},5000);return()=>clearInterval(timer)});
</script>

<V2Section title="Booru model"><V2Card><V2Stack gap="sm">
  {#if settings}
    <V2SelectField id="booru-model" label="Model" value={settings.model_repo} options={modelOptions} onchange={(value)=>settings={...settings!,model_repo:value}}/>
    <p class="v2-small v2-muted">{currentModel?.cached?'Downloaded':'Not downloaded'} · {currentModel?.loaded?'Loaded in memory':'Unloaded'}{#if currentModel} · Revision {currentModel.revision.slice(0,12)}{/if}</p>
    <V2Button disabled={busy||downloadActive} onclick={()=>void download()}>{currentModel?.cached?'Check and download model':'Download selected model'}</V2Button>
    {#if currentDownload}
      <div role="status" aria-live="polite" class="booru-download-progress">
        <span>Model download: {currentDownload.status}{#if downloadPercent!==null} · {Math.round(downloadPercent)}%{/if}</span>
        {#if downloadActive}
          <V2Progress value={downloadPercent??undefined} indeterminate={downloadPercent===null} label="Booru model download progress"/>
          <span class="v2-small v2-muted">{downloadDetail}</span>
        {:else if currentDownload.error}<span class="v2-small">{currentDownload.error.message}</span>{/if}
      </div>
    {/if}
    <label for="booru-idle">Unload model after inactivity (seconds; 0 unloads after each image)</label>
    <input id="booru-idle" type="number" min="0" max="86400" value={settings.idle_seconds} oninput={(event)=>settings={...settings!,idle_seconds:Number(event.currentTarget.value)}}/>
    <V2Checkbox label="Unload model after each tagging run" checked={settings.unload_model_after_run} onchange={(value)=>settings={...settings!,unload_model_after_run:value}}/>
    <p class="v2-small v2-muted">Models download to the mapped /cache/booru-models folder. SwinV2 keeps predictions comparable with immich-booru-tagger. Smaller models can change predictions.</p>
    <label for="booru-confidence">General and rating threshold</label><input id="booru-confidence" type="number" min="0" max="1" step="0.01" value={settings.confidence_threshold} oninput={(event)=>settings={...settings!,confidence_threshold:Number(event.currentTarget.value)}}/>
    <label for="booru-character">Character threshold</label><input id="booru-character" type="number" min="0" max="1" step="0.01" value={settings.character_threshold} oninput={(event)=>settings={...settings!,character_threshold:Number(event.currentTarget.value)}}/>
    <label for="booru-processed-tag">Processed marker tag</label><input id="booru-processed-tag" type="text" maxlength="255" value={settings.processed_tag_name} oninput={(event)=>settings={...settings!,processed_tag_name:event.currentTarget.value}}/>
    <p class="v2-small v2-muted">Added to each successfully tagged image so you can find it in Immich. Leave empty to skip the marker. Undo removes only markers added by that run.</p>
    <label for="booru-rating-parent">Content rating parent tag</label><input id="booru-rating-parent" type="text" maxlength="255" value={settings.content_rating_tag_name} oninput={(event)=>settings={...settings!,content_rating_tag_name:event.currentTarget.value}}/>
  {:else}<p>Loading Booru settings…</p>{/if}
</V2Stack></V2Card></V2Section>
<V2Section title="Automatic tagging"><V2Card><V2Stack gap="sm">
  {#if schedule&&settings}<V2Checkbox label="Enable scheduled Booru tagging" checked={schedule.enabled} onchange={(value)=>schedule={...schedule!,enabled:value}}/><V2CronField id="booru-cron" label="Scheduled tagging" enabled={schedule.enabled} lastRunAt={schedule.last_run_at} value={schedule.cron_expression??'0 */2 * * *'} onchange={(value)=>schedule={...schedule!,cron_expression:value}}/>
    <label for="booru-target-albums">Target albums (comma separated)</label><input id="booru-target-albums" type="text" value={settings.target_albums} placeholder="Anime,Hentai" oninput={(event)=>settings={...settings!,target_albums:event.currentTarget.value}}/>
    <p class="v2-small v2-muted">Empty: process images with no tags. With albums: process images in any named album unless they already have the marker tag.</p>
    <label for="booru-batch">Images per batch</label><input id="booru-batch" type="number" min="1" max="1000" value={settings.batch_size} oninput={(event)=>settings={...settings!,batch_size:Number(event.currentTarget.value)}}/>
    <label for="booru-max-batches">Maximum batches per scheduled run</label><input id="booru-max-batches" type="number" min="1" max="100" value={settings.max_batches_per_run} oninput={(event)=>settings={...settings!,max_batches_per_run:Number(event.currentTarget.value)}}/>
    <label for="booru-failure-timeout">Maximum failed attempts (0 disables scheduled retries)</label><input id="booru-failure-timeout" type="number" min="0" max="100" value={settings.failure_timeout} oninput={(event)=>settings={...settings!,failure_timeout:Number(event.currentTarget.value)}}/>
    <label for="booru-tag-cache-ttl">Tag catalog cache (seconds)</label><input id="booru-tag-cache-ttl" type="number" min="1" max="86400" value={settings.tag_cache_ttl} oninput={(event)=>settings={...settings!,tag_cache_ttl:Number(event.currentTarget.value)}}/>
    <V2SelectField id="booru-log-level" label="Booru log level" value={settings.log_level} options={['DEBUG','INFO','WARNING','ERROR','CRITICAL'].map((value)=>({value,label:value}))} onchange={(value)=>settings={...settings!,log_level:value}}/>
    <p class="v2-small v2-muted">Failed images wait at least one hour before another scheduled attempt. New images run first; you can retry failures immediately below.</p>
  {/if}
  <V2Button variant="primary" disabled={busy||!settings||!schedule} onclick={()=>void save()}>Save Booru settings</V2Button>
  {#if error}<p role="alert">{error}</p>{/if}{#if message}<p role="status">{message}</p>{/if}
</V2Stack></V2Card></V2Section>
<V2Section title="Tagging runs"><V2Stack gap="sm">
  {#each runs as run (run.id)}<V2Card><V2Stack gap="sm">
    <div style="display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap"><span>{new Date(run.created_at).toLocaleString()} · {tasks.find((task)=>task.id===run.id)?.status??'Finished'} · {tasks.find((task)=>task.id===run.id)?.counters?.completed??0} tagged · {tasks.find((task)=>task.id===run.id)?.counters?.failed??run.failures} failed</span><div style="display:flex;gap:.5rem;flex-wrap:wrap">{#if run.failures}<V2Button disabled={busy} onclick={()=>void toggleFailures(run)}>{openRun===run.id?'Hide failures':'Show failures'}</V2Button><V2Button disabled={busy} onclick={()=>void retry(run)}>Retry failed</V2Button>{/if}<V2Button disabled={busy||Boolean(run.undone_at)||!['completed','failed','cancelled'].includes(tasks.find((task)=>task.id===run.id)?.status??'completed')} onclick={()=>void undo(run)}>{run.undone_at?'Undone':'Undo added tags'}</V2Button></div></div>
    {#if tasks.find((task)=>task.id===run.id)?.error}<p class="v2-small" role="status">{tasks.find((task)=>task.id===run.id)?.error?.message}</p>{/if}
    {#if openRun===run.id}{#each failures as failure (failure.asset_id)}<p class="v2-small">{failure.asset_id}: {failure.error} · attempt {failure.attempts} · next scheduled retry {new Date(failure.next_retry_at).toLocaleString()}</p>{/each}{/if}
  </V2Stack></V2Card>{:else}<p class="v2-small v2-muted">No tagging runs yet.</p>{/each}
</V2Stack></V2Section>

<style>
  .booru-download-progress{display:grid;gap:.35rem}
</style>
