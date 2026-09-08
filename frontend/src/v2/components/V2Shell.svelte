<script lang="ts">
  import { Album, BookOpen, CircleGauge, Copy, Ellipsis, Images, RotateCcw, Settings, Tags } from '@lucide/svelte';
  import { onMount, tick } from 'svelte';
  import { libraryData } from '../data/currentDataSource.svelte';
  import type { SyncCoordinatorStatus, SyncRun, TaskSubscription } from '../data/syncContracts';
  import { readV2Density, V2_DENSITY_EVENT, writeV2Density, type V2Density } from '../state/density';
  import V2Button from './V2Button.svelte';
  import V2Progress from './V2Progress.svelte';
  import V2Segmented from './V2Segmented.svelte';
  import V2TaskBubble from './V2TaskBubble.svelte';

  type NavItem = { key:string; label:string; href:string; group?:string; position?:'top'|'bottom' };

  const TASK_TRAY_STORAGE_KEY='immich-companion-v2-task-tray-expanded';
  function readTaskExpanded():boolean{
    if(typeof localStorage==='undefined')return true;
    const stored=localStorage.getItem(TASK_TRAY_STORAGE_KEY);
    return stored===null?true:stored==='true';
  }
  function writeTaskExpanded(expanded:boolean):void{
    if(typeof localStorage==='undefined')return;
    localStorage.setItem(TASK_TRAY_STORAGE_KEY,String(expanded));
  }

  let { activeKey, title, navItems, onnavigate, brand='Immich Companion', connectionLabel='Immich connected', children }: { activeKey:string; title:string; navItems:NavItem[]; onnavigate:(key:string)=>void; brand?:string; connectionLabel?:string; children:import('svelte').Snippet } = $props();
  let density=$state<V2Density>('standard'), taskExpanded=$state(readTaskExpanded()), root=$state<HTMLDivElement>();
  let syncStatus=$state<SyncCoordinatorStatus | null>(null), syncStatusError=$state(false), taskSubscription=$state<TaskSubscription | null>(null);
  let active=true;
  let pollTimer:ReturnType<typeof setInterval> | null=null;

  function groupItems(items:NavItem[]){const groups:{label:string;items:NavItem[]}[]=[];for(const item of items){const label=item.group??'';let group=groups.find((entry)=>entry.label===label);if(!group){group={label,items:[]};groups.push(group)}group.items.push(item)}return groups}
  const topGroups=$derived(groupItems(navItems.filter((item)=>item.position!=='bottom'))), bottomGroups=$derived(groupItems(navItems.filter((item)=>item.position==='bottom')));
  const mobileItems=$derived([
    {key:'status',label:'Status'},
    {key:'assets',label:'Assets'},
    {key:'duplicates',label:'Review'},
    {key:'albums',label:'Manage'},
    {key:'settings',label:'More'},
  ].map((mobileItem)=>({ ...mobileItem, href:navItems.find((item)=>item.key===mobileItem.key)?.href??`/v2/${mobileItem.key}` })));
  const currentRun=$derived(syncStatus?.active ?? syncStatus?.pending ?? null);
  const progressKnown=$derived(currentRun?.progress.total != null && currentRun.progress.percent != null);
  const taskOverlayVisible=$derived(taskExpanded || currentRun !== null);

  function setDensity(next:V2Density){density=next;writeV2Density(next)}
  function setTaskExpanded(expanded:boolean){taskExpanded=expanded;writeTaskExpanded(expanded)}

  function handleNavigation(event:MouseEvent,item:NavItem):void{
    if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    event.preventDefault();
    onnavigate(item.key);
  }

  function syncTaskBounds(): void {
    if (!root) return;
    const content = root.querySelector<HTMLElement>('.v2-content');
    if (!content) return;
    const rect = content.getBoundingClientRect();
    root.style.setProperty('--v2-task-left', `${Math.max(9, rect.left + 18)}px`);
    root.style.setProperty('--v2-task-right', `${Math.max(9, window.innerWidth - rect.right + 18)}px`);
  }

  function runLabel(run:SyncRun | null):string{
    if(!run)return 'No synchronization running';
    const mode=run.mode==='full'?'Global':'Incremental';
    const phase=run.progress.phase || run.phase;
    return `${mode} sync · ${phase}`;
  }

  function progressDetail(run:SyncRun):string{
    if(run.progress.detail)return run.progress.detail;
    if(run.progress.total != null)return `${run.progress.completed.toLocaleString()} of ${run.progress.total.toLocaleString()} processed`;
    return `${run.progress.completed.toLocaleString()} processed · total work not known yet`;
  }

  async function refreshSyncStatus():Promise<void>{
    try{
      const next=await libraryData.sync.status();
      if(!active)return;
      syncStatus=next;
      syncStatusError=false;
    }catch{
      if(active)syncStatusError=true;
    }
  }

  onMount(()=>{
    active=true;
    density=readV2Density();
    void refreshSyncStatus();
    taskSubscription=libraryData.tasks.subscribe({
      onTask:(task)=>{if(task.taskType==='asset_sync')void refreshSyncStatus()},
      onConnectionState:(state)=>{if(state==='connected')void refreshSyncStatus()},
      onError:()=>undefined,
    });
    pollTimer=setInterval(()=>void refreshSyncStatus(),10000);
    const onDensity=(event:Event)=>density=(event as CustomEvent<V2Density>).detail;
    const observer=new ResizeObserver(syncTaskBounds);
    if(root) observer.observe(root);
    window.addEventListener(V2_DENSITY_EVENT,onDensity);
    window.addEventListener('resize',syncTaskBounds);
    void tick().then(syncTaskBounds);
    return()=>{
      active=false;
      observer.disconnect();
      window.removeEventListener(V2_DENSITY_EVENT,onDensity);
      window.removeEventListener('resize',syncTaskBounds);
      if(pollTimer)clearInterval(pollTimer);
      taskSubscription?.close();
      taskSubscription=null;
    }
  });

  $effect(()=>{
    activeKey;
    density;
    void tick().then(syncTaskBounds);
  });
</script>

{#snippet navIcon(key:string)}
  <span class="v2-nav-icon" aria-hidden="true">
    {#if key==='status'}<CircleGauge size={17}/>{:else if key==='assets'}<Images size={17}/>{:else if key==='restore'}<RotateCcw size={17}/>{:else if key==='duplicates'}<Copy size={17}/>{:else if key==='albums'}<Album size={17}/>{:else if key==='tags'}<Tags size={17}/>{:else if key==='settings'}<Settings size={17}/>{:else if key==='docs'}<BookOpen size={17}/>{:else}<CircleGauge size={17}/>{/if}
  </span>
{/snippet}

<div class="v2-root" data-density={density} data-task-overlay={taskOverlayVisible || undefined} bind:this={root}>
  <div class="v2-app">
    <aside class="v2-sidebar">
      <div class="v2-brand"><div class="v2-logo"></div><span class="v2-brand-text">{brand}</span></div>
      {#each topGroups as group (group.label)}
        {#if group.label}<div class="v2-nav-label">{group.label}</div>{/if}
        <nav class="v2-nav" aria-label={group.label||'Navigation'}>{#each group.items as item (item.key)}<a class="v2-nav-button" href={item.href} aria-current={item.key===activeKey?'page':undefined} onclick={(event)=>handleNavigation(event,item)}>{@render navIcon(item.key)}<span class="v2-nav-text">{item.label}</span></a>{/each}</nav>
      {/each}
      <div class="v2-grow"></div>
      {#each bottomGroups as group (group.label)}<nav class="v2-nav" aria-label={group.label||'Secondary navigation'}>{#each group.items as item (item.key)}<a class="v2-nav-button" href={item.href} aria-current={item.key===activeKey?'page':undefined} onclick={(event)=>handleNavigation(event,item)}>{@render navIcon(item.key)}<span class="v2-nav-text">{item.label}</span></a>{/each}</nav>{/each}
      <div class="v2-connection"><span class="v2-dot"></span>{connectionLabel} <small class="v2-muted">v2.x</small></div>
    </aside>

    <div class="v2-shell">
      <header class="v2-topbar"><div class="v2-crumb">{brand} / <span class="v2-crumb-current">{title}</span></div><div class="v2-top-actions"><input class="v2-top-search" placeholder="Search current interface…" aria-label="Search current interface"><V2Segmented items={['Standard','Condensed']} active={density==='standard'?'Standard':'Condensed'} onselect={(value)=>setDensity(value==='Standard'?'standard':'condensed')} ariaLabel="Interface density" /><V2Button onclick={()=>setTaskExpanded(true)}>Tasks</V2Button><V2Button ariaLabel="More actions"><Ellipsis size={18} strokeWidth={2.1}/></V2Button></div></header>
      {@render children()}
    </div>
  </div>

  {#if taskExpanded}
    <div class="v2-tasktray">
      <div class="v2-tasktray-head">
        <div class="v2-task-summary">
          <span class="v2-task-status-dot" aria-hidden="true"></span>
          <div><b>Synchronization</b><small class="v2-muted">{runLabel(currentRun)}</small></div>
        </div>
        <small class="v2-task-overview v2-muted">
          {#if currentRun}
            {progressKnown ? 'Live determinate progress' : 'Live progress · total pending'}
          {:else if syncStatusError}
            Status temporarily unavailable
          {:else}
            Idle
          {/if}
        </small>
        <V2Button onclick={()=>setTaskExpanded(false)}>Collapse</V2Button>
      </div>
      <div class="v2-task-list">
        {#if currentRun}
          <div class="v2-task-row">
            <span class="v2-task-runner" aria-hidden="true"></span>
            <div class="v2-task-copy"><span>{runLabel(currentRun)}</span><small class="v2-muted">{progressDetail(currentRun)}</small></div>
            <div class="v2-task-progress">
              <div class="v2-task-progress-meta">
                <small>{currentRun.progress.completed.toLocaleString()} processed</small>
                <small>{progressKnown ? `${currentRun.progress.percent}%` : 'Unknown total'}</small>
              </div>
              <V2Progress
                value={progressKnown ? currentRun.progress.percent ?? undefined : undefined}
                indeterminate={!progressKnown}
                label={`${runLabel(currentRun)} progress`}
              />
            </div>
            <span class="v2-task-stat">{progressKnown ? `${currentRun.progress.percent}%` : '—'}</span>
          </div>
        {:else}
          <div class="v2-task-row">
            <div class="v2-task-copy"><span>No synchronization is running</span><small class="v2-muted">Start a global or incremental sync from Settings → Sync.</small></div>
          </div>
        {/if}
      </div>
    </div>
  {:else if currentRun}
    <div class="v2-task-bubbles" aria-label="Collapsed synchronization task">
      <V2TaskBubble
        value={progressKnown ? currentRun.progress.percent ?? undefined : undefined}
        indeterminate={!progressKnown}
        label={runLabel(currentRun)}
        detail={progressDetail(currentRun)}
        onclick={()=>setTaskExpanded(true)}
      />
    </div>
  {/if}

  <nav class="v2-mobile-nav" aria-label="Mobile navigation">{#each mobileItems as item (item.key)}<a href={item.href} aria-current={item.key===activeKey?'page':undefined} onclick={(event)=>handleNavigation(event,item)}>{item.label}</a>{/each}</nav>
</div>
