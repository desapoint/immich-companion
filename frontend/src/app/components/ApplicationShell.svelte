<script lang="ts">
  import { Album, BookOpen, CircleGauge, Copy, Ellipsis, Images, RotateCcw, Settings, Tags, TriangleAlert } from '@lucide/svelte';
  import { onMount, tick } from 'svelte';
  import type { SyncRun } from '../../features/status/types/syncContracts';
  import { formatTaskProgressPercent } from '../../features/status/utils/taskProgress';
  import { backgroundTaskPresentation, backgroundTaskStatus } from '../../features/status/state/backgroundTaskStatus.svelte';
  import { syncStatus } from '../../features/status/state/syncStatus.svelte';
  import { connectionLabel } from '../../features/status/utils/connectionPresentation';
  import V2Button from '../../lib/components/ui/Button.svelte';
  import V2Progress from '../../lib/components/ui/Progress.svelte';
  import V2TaskBubble from '../../features/status/components/TaskBubble.svelte';
  import { pagePath } from '../navigation';

  type NavItem = { key:string; label:string; href:string; group?:string; position?:'top'|'bottom' };

  let { activeKey, title, navItems, onnavigate, brand='Immich Companion', children }: { activeKey:string; title:string; navItems:NavItem[]; onnavigate:(key:string)=>void; brand?:string; children:import('svelte').Snippet } = $props();
  let taskExpanded=$state(true), mobileMenuOpen=$state(false), root=$state<HTMLDivElement>();

  function groupItems(items:NavItem[]){const groups:{label:string;items:NavItem[]}[]=[];for(const item of items){const label=item.group??'';let group=groups.find((entry)=>entry.label===label);if(!group){group={label,items:[]};groups.push(group)}group.items.push(item)}return groups}
  const topGroups=$derived(groupItems(navItems.filter((item)=>item.position!=='bottom'))), bottomGroups=$derived(groupItems(navItems.filter((item)=>item.position==='bottom')));
  const mobileItems=$derived([
    {key:'status',label:'Status'},
    {key:'assets',label:'Assets'},
    {key:'duplicates',label:'Review'},
    {key:'albums',label:'Manage'},
  ].map((mobileItem)=>({ ...mobileItem, href:navItems.find((item)=>item.key===mobileItem.key)?.href??pagePath(mobileItem.key as Parameters<typeof pagePath>[0]) })));
  const mobileMenuItems=$derived(navItems.filter((item)=>['restore','albums','tags','similarity-debug','errors','settings','docs'].includes(item.key)));
  const mobileMenuActive=$derived(mobileMenuItems.some((item)=>item.key===activeKey));
  const currentRun=$derived(syncStatus.status?.active ?? syncStatus.status?.pending ?? null);
  const progressKnown=$derived(currentRun?.progress.total != null && currentRun.progress.percent != null);
  const backgroundTasks=$derived(backgroundTaskStatus.workflow?[backgroundTaskStatus.workflow]:backgroundTaskStatus.tasks.map((task)=>({id:task.id,presentation:backgroundTaskPresentation(task)})));
  const activeTaskCount=$derived((currentRun?1:0)+backgroundTasks.length);
  const taskOverlayVisible=$derived(activeTaskCount>0);

  function setTaskExpanded(expanded:boolean){taskExpanded=expanded}

  function handleNavigation(event:MouseEvent,item:NavItem):void{
    if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return;
    event.preventDefault();
    mobileMenuOpen=false;
    onnavigate(item.key);
  }

  function handleWindowKeydown(event:KeyboardEvent):void{
    if(event.key==='Escape')mobileMenuOpen=false;
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

  onMount(()=>{
    const releaseSyncStatus=syncStatus.acquire();
    const releaseBackgroundTasks=backgroundTaskStatus.acquire();
    const observer=new ResizeObserver(syncTaskBounds);
    if(root) observer.observe(root);
    window.addEventListener('resize',syncTaskBounds);
    void tick().then(syncTaskBounds);
    return()=>{
      releaseSyncStatus();
      releaseBackgroundTasks();
      observer.disconnect();
      window.removeEventListener('resize',syncTaskBounds);
    }
  });

  $effect(()=>{
    activeKey;
    void tick().then(syncTaskBounds);
  });
</script>

<svelte:window onkeydown={handleWindowKeydown}/>

{#snippet navIcon(key:string)}
  <span class="v2-nav-icon" aria-hidden="true">
    {#if key==='status'}<CircleGauge size={17}/>{:else if key==='errors'}<TriangleAlert size={17}/>{:else if key==='assets'}<Images size={17}/>{:else if key==='restore'}<RotateCcw size={17}/>{:else if key==='duplicates'}<Copy size={17}/>{:else if key==='albums'}<Album size={17}/>{:else if key==='tags'}<Tags size={17}/>{:else if key==='settings'}<Settings size={17}/>{:else if key==='docs'}<BookOpen size={17}/>{:else}<CircleGauge size={17}/>{/if}
  </span>
{/snippet}

<div class="v2-root" data-density="condensed" data-task-overlay={taskOverlayVisible || undefined} bind:this={root}>
  <div class="v2-app">
    <aside class="v2-sidebar">
      <div class="v2-brand"><div class="v2-logo"></div><span class="v2-brand-text">{brand}</span></div>
      {#each topGroups as group (group.label)}
        {#if group.label}<div class="v2-nav-label">{group.label}</div>{/if}
        <nav class="v2-nav" aria-label={group.label||'Navigation'}>{#each group.items as item (item.key)}<a class="v2-nav-button" href={item.href} aria-current={item.key===activeKey?'page':undefined} onclick={(event)=>handleNavigation(event,item)}>{@render navIcon(item.key)}<span class="v2-nav-text">{item.label}</span></a>{/each}</nav>
      {/each}
      <div class="v2-grow"></div>
      {#each bottomGroups as group (group.label)}<nav class="v2-nav" aria-label={group.label||'Secondary navigation'}>{#each group.items as item (item.key)}<a class="v2-nav-button" href={item.href} aria-current={item.key===activeKey?'page':undefined} onclick={(event)=>handleNavigation(event,item)}>{@render navIcon(item.key)}<span class="v2-nav-text">{item.label}</span></a>{/each}</nav>{/each}
      <div class="v2-connection" title="Task-stream connection for live updates; this does not represent overall Immich or server health."><span class="v2-dot"></span><span>{connectionLabel(syncStatus.connectionState)}</span><small class="v2-muted">Task updates · v2.x</small></div>
    </aside>

    <div class="v2-shell">
      <header class="v2-topbar"><div class="v2-crumb">{brand} / <span class="v2-crumb-current">{title}</span></div></header>
      {@render children()}
    </div>
  </div>

  {#if taskExpanded && activeTaskCount > 0}
    <div class="v2-tasktray">
      <div class="v2-tasktray-head">
        <div class="v2-task-summary">
          <span class="v2-task-status-dot" aria-hidden="true"></span>
          <div><b>Background tasks</b><small class="v2-muted">{activeTaskCount ? `${activeTaskCount} active` : 'No active work'}</small></div>
        </div>
        <small class="v2-task-overview v2-muted">
          {#if activeTaskCount}
            Live task progress
          {:else if syncStatus.error || backgroundTaskStatus.error}
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
                <small>{progressKnown ? formatTaskProgressPercent(currentRun.progress.percent!) : 'Unknown total'}</small>
              </div>
              <V2Progress
                value={progressKnown ? currentRun.progress.percent ?? undefined : undefined}
                indeterminate={!progressKnown}
                label={`${runLabel(currentRun)} progress`}
              />
            </div>
            <span class="v2-task-stat">{progressKnown ? formatTaskProgressPercent(currentRun.progress.percent!) : '—'}</span>
          </div>
        {/if}
        {#each backgroundTasks as item (item.id)}
          <div class="v2-task-row">
            <span class="v2-task-runner" aria-hidden="true"></span>
            <div class="v2-task-copy"><span>{item.presentation.label}</span><small class="v2-muted">{item.presentation.detail}</small></div>
            <div class="v2-task-progress">
              <div class="v2-task-progress-meta">
                <small>{item.presentation.total === null ? `${item.presentation.completed.toLocaleString()} processed` : `${item.presentation.completed.toLocaleString()} of ${item.presentation.total.toLocaleString()} processed`}</small>
                <small>{item.presentation.total !== null && item.presentation.percent !== null ? formatTaskProgressPercent(item.presentation.percent) : 'Unknown total'}</small>
              </div>
              <V2Progress
                value={item.presentation.total !== null ? item.presentation.percent ?? undefined : undefined}
                indeterminate={item.presentation.total === null || item.presentation.percent === null}
                label={`${item.presentation.label} progress`}
              />
            </div>
            <span class="v2-task-stat">{item.presentation.total !== null && item.presentation.percent !== null ? formatTaskProgressPercent(item.presentation.percent) : '—'}</span>
          </div>
        {/each}
      </div>
    </div>
  {:else if activeTaskCount}
    <div class="v2-task-bubbles" aria-label="Collapsed background tasks">
      {#if currentRun}<V2TaskBubble value={progressKnown ? currentRun.progress.percent ?? undefined : undefined} indeterminate={!progressKnown} label={runLabel(currentRun)} detail={progressDetail(currentRun)} onclick={()=>setTaskExpanded(true)}/>{/if}
      {#each backgroundTasks as item (item.id)}<V2TaskBubble value={item.presentation.total!==null?item.presentation.percent??undefined:undefined} indeterminate={item.presentation.total===null||item.presentation.percent===null} label={item.presentation.label} detail={item.presentation.detail} onclick={()=>setTaskExpanded(true)}/>{/each}
    </div>
  {/if}

  {#if mobileMenuOpen}
    <div class="v2-mobile-more-menu" role="dialog" aria-label="More navigation">
      <div class="v2-mobile-more-head"><b>More destinations</b><button type="button" onclick={()=>mobileMenuOpen=false}>Close</button></div>
      <nav aria-label="Additional mobile navigation">
        {#each mobileMenuItems as item (item.key)}
          <a href={item.href} aria-current={item.key===activeKey?'page':undefined} onclick={(event)=>handleNavigation(event,item)}>{@render navIcon(item.key)}<span>{item.label}</span></a>
        {/each}
      </nav>
    </div>
  {/if}
  <nav class="v2-mobile-nav" aria-label="Mobile navigation">
    {#each mobileItems as item (item.key)}<a href={item.href} aria-current={item.key===activeKey?'page':undefined} onclick={(event)=>handleNavigation(event,item)}>{@render navIcon(item.key)}<span>{item.label}</span></a>{/each}
    <button type="button" aria-expanded={mobileMenuOpen} aria-current={mobileMenuActive?'page':undefined} onclick={()=>mobileMenuOpen=!mobileMenuOpen}><span class="v2-nav-icon" aria-hidden="true"><Ellipsis size={18}/></span><span>More</span></button>
  </nav>
</div>
