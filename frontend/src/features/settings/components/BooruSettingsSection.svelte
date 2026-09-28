<script lang="ts">
  import { onMount } from 'svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Checkbox from '../../../lib/components/ui/Checkbox.svelte';
  import V2CronField from '../../../lib/components/ui/CronField.svelte';
  import V2SelectField from '../../../lib/components/ui/SimpleSelectField.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';

  type Settings = {model_repo:string;idle_seconds:number;confidence_threshold:number;character_threshold:number;models:string[]};
  type Schedule = {name:string;enabled:boolean;cron_expression:string|null;last_run_at:string|null};
  type Run = {id:string;created_at:string;undone_at:string|null};
  let settings=$state<Settings|null>(null),schedule=$state<Schedule|null>(null),runs=$state<Run[]>([]),busy=$state(false),error=$state(''),message=$state('');
  const modelOptions=[
    {value:'SmilingWolf/wd-swinv2-tagger-v3',label:'SwinV2 v3 · same as existing tagger'},
    {value:'SmilingWolf/wd-convnext-tagger-v3',label:'ConvNeXt v3 · smaller model'},
    {value:'SmilingWolf/wd-vit-tagger-v3',label:'ViT v3 · smaller model'},
  ];
  async function api<T>(path:string,init?:RequestInit):Promise<T>{const response=await fetch(path,init);if(!response.ok){const body=await response.json().catch(()=>null) as {detail?:string}|null;throw new Error(body?.detail??`Request failed (${response.status})`)}return response.json() as Promise<T>}
  function json(value:unknown):RequestInit{return{method:'PUT',headers:{'content-type':'application/json'},body:JSON.stringify(value)}}
  async function load(){try{const [next,schedules,history]=await Promise.all([api<Settings>('/api/booru/settings'),api<Schedule[]>('/api/settings/sync'),api<Run[]>('/api/booru/runs')]);settings=next;schedule=schedules.find((item)=>item.name==='booru-tagging')??null;runs=history}catch(value){error=value instanceof Error?value.message:'Booru settings could not be loaded.'}}
  async function save(){if(!settings||!schedule||busy)return;busy=true;error='';message='';try{await api('/api/booru/settings',json(settings));schedule=await api<Schedule>(`/api/settings/sync/${schedule.name}`,json({enabled:schedule.enabled,cron_expression:schedule.cron_expression}));message='Booru settings saved.'}catch(value){error=value instanceof Error?value.message:'Booru settings could not be saved.'}finally{busy=false}}
  async function undo(run:Run){if(busy)return;busy=true;error='';message='';try{const result=await api<{assets:number;tags:number}>(`/api/booru/runs/${run.id}/undo`,{method:'POST'});message=`Removed ${result.tags} Booru tags from ${result.assets} assets.`;runs=await api<Run[]>('/api/booru/runs')}catch(value){error=value instanceof Error?value.message:'Undo failed. Retry this run.'}finally{busy=false}}
  onMount(()=>{void load()});
</script>

<V2Section title="Booru model"><V2Card><V2Stack gap="sm">
  {#if settings}
    <V2SelectField id="booru-model" label="Model" value={settings.model_repo} options={modelOptions} onchange={(value)=>settings={...settings!,model_repo:value}}/>
    <label for="booru-idle">Unload model after inactivity (seconds; 0 unloads after each image)</label>
    <input id="booru-idle" type="number" min="0" max="86400" value={settings.idle_seconds} oninput={(event)=>settings={...settings!,idle_seconds:Number(event.currentTarget.value)}}/>
    <p class="v2-small v2-muted">Models download on first use to the mapped /cache/booru-models folder. SwinV2 keeps predictions comparable with immich-booru-tagger. Smaller models can change predictions.</p>
    <label for="booru-confidence">General and rating threshold</label><input id="booru-confidence" type="number" min="0" max="1" step="0.01" value={settings.confidence_threshold} oninput={(event)=>settings={...settings!,confidence_threshold:Number(event.currentTarget.value)}}/>
    <label for="booru-character">Character threshold</label><input id="booru-character" type="number" min="0" max="1" step="0.01" value={settings.character_threshold} oninput={(event)=>settings={...settings!,character_threshold:Number(event.currentTarget.value)}}/>
  {:else}<p>Loading Booru settings…</p>{/if}
</V2Stack></V2Card></V2Section>
<V2Section title="Automatic tagging"><V2Card><V2Stack gap="sm">
  {#if schedule}<V2Checkbox label="Enable scheduled Booru tagging" checked={schedule.enabled} onchange={(value)=>schedule={...schedule!,enabled:value}}/><V2CronField id="booru-cron" label="Tag up to 250 unprocessed images per run" enabled={schedule.enabled} lastRunAt={schedule.last_run_at} value={schedule.cron_expression??'0 2 * * *'} onchange={(value)=>schedule={...schedule!,cron_expression:value}}/>{/if}
  <V2Button variant="primary" disabled={busy||!settings||!schedule} onclick={()=>void save()}>Save Booru settings</V2Button>
  {#if error}<p role="alert">{error}</p>{/if}{#if message}<p role="status">{message}</p>{/if}
</V2Stack></V2Card></V2Section>
<V2Section title="Undo tagging runs"><V2Stack gap="sm">
  {#each runs as run (run.id)}<V2Card><div style="display:flex;align-items:center;justify-content:space-between;gap:1rem"><span>{new Date(run.created_at).toLocaleString()}</span><V2Button disabled={busy||Boolean(run.undone_at)} onclick={()=>void undo(run)}>{run.undone_at?'Undone':'Undo added tags'}</V2Button></div></V2Card>{:else}<p class="v2-small v2-muted">No tagging runs yet.</p>{/each}
</V2Stack></V2Section>
