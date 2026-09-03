<script lang="ts">
  import { onMount, tick } from 'svelte';
  import { readV2Density, V2_DENSITY_EVENT, writeV2Density, type V2Density } from '../state/density';
  import V2Button from './V2Button.svelte';
  import V2Segmented from './V2Segmented.svelte';

  type NavItem = { key:string; label:string; group?:string; position?:'top'|'bottom' };

  let { activeKey, title, navItems, onnavigate, brand='Immich Companion', connectionLabel='Immich connected', children }: { activeKey:string; title:string; navItems:NavItem[]; onnavigate:(key:string)=>void; brand?:string; connectionLabel?:string; children:import('svelte').Snippet } = $props();
  let density=$state<V2Density>('standard'), taskVisible=$state(true), root=$state<HTMLDivElement>();

  function groupItems(items:NavItem[]){const groups:{label:string;items:NavItem[]}[]=[];for(const item of items){const label=item.group??'';let group=groups.find((entry)=>entry.label===label);if(!group){group={label,items:[]};groups.push(group)}group.items.push(item)}return groups}
  const topGroups=$derived(groupItems(navItems.filter((item)=>item.position!=='bottom'))), bottomGroups=$derived(groupItems(navItems.filter((item)=>item.position==='bottom')));
  const mobileItems=[{key:'status',label:'Status'},{key:'assets',label:'Assets'},{key:'duplicates',label:'Review'},{key:'albums',label:'Manage'},{key:'settings',label:'More'}];
  function setDensity(next:V2Density){density=next;writeV2Density(next)}

  function syncTaskBounds(): void {
    if (!root) return;
    const content = root.querySelector<HTMLElement>('.v2-content');
    if (!content) return;
    const rect = content.getBoundingClientRect();
    root.style.setProperty('--v2-task-left', `${Math.max(9, rect.left + 18)}px`);
    root.style.setProperty('--v2-task-right', `${Math.max(9, window.innerWidth - rect.right + 18)}px`);
  }

  onMount(()=>{
    density=readV2Density();
    const onDensity=(event:Event)=>density=(event as CustomEvent<V2Density>).detail;
    const observer=new ResizeObserver(syncTaskBounds);
    if(root) observer.observe(root);
    window.addEventListener(V2_DENSITY_EVENT,onDensity);
    window.addEventListener('resize',syncTaskBounds);
    void tick().then(syncTaskBounds);
    return()=>{
      observer.disconnect();
      window.removeEventListener(V2_DENSITY_EVENT,onDensity);
      window.removeEventListener('resize',syncTaskBounds);
    }
  });

  $effect(()=>{
    activeKey;
    density;
    void tick().then(syncTaskBounds);
  });
</script>

<div class="v2-root" data-density={density} bind:this={root}>
  <div class="v2-app">
    <aside class="v2-sidebar">
      <div class="v2-brand"><div class="v2-logo"></div><span class="v2-brand-text">{brand}</span></div>
      {#each topGroups as group}
        {#if group.label}<div class="v2-nav-label">{group.label}</div>{/if}
        <nav class="v2-nav" aria-label={group.label||'Navigation'}>{#each group.items as item}<button class="v2-nav-button" aria-current={item.key===activeKey?'page':undefined} onclick={()=>onnavigate(item.key)}><i class="v2-nav-icon" aria-hidden="true"></i><span class="v2-nav-text">{item.label}</span></button>{/each}</nav>
      {/each}
      <div class="v2-grow"></div>
      {#each bottomGroups as group}<nav class="v2-nav" aria-label={group.label||'Secondary navigation'}>{#each group.items as item}<button class="v2-nav-button" aria-current={item.key===activeKey?'page':undefined} onclick={()=>onnavigate(item.key)}><i class="v2-nav-icon" aria-hidden="true"></i><span class="v2-nav-text">{item.label}</span></button>{/each}</nav>{/each}
      <div class="v2-connection"><span class="v2-dot"></span>{connectionLabel} <small class="v2-muted">v2.x</small></div>
    </aside>

    <div class="v2-shell">
      <header class="v2-topbar">
        <div class="v2-crumb">{brand} / <span class="v2-crumb-current">{title}</span></div>
        <div class="v2-top-actions">
          <input class="v2-top-search" placeholder="Search current interface…" aria-label="Search current interface">
          <V2Segmented items={['Standard','Condensed']} active={density==='standard'?'Standard':'Condensed'} onselect={(value)=>setDensity(value==='Standard'?'standard':'condensed')} ariaLabel="Interface density" />
          <V2Button onclick={()=>taskVisible=!taskVisible}>Tasks</V2Button>
          <V2Button ariaLabel="More actions">⋯</V2Button>
        </div>
      </header>
      {@render children()}
    </div>
  </div>

  {#if taskVisible}
    <div class="v2-tasktray">
      <div class="v2-task-summary"><b>Background tasks</b><small class="v2-muted">Scanning asset changes · 62%</small></div>
      <div class="v2-task-actions"><div class="v2-progress" role="progressbar" aria-label="Background task progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="62"><i></i></div><V2Button onclick={()=>taskVisible=false}>Hide</V2Button></div>
    </div>
  {/if}

  <nav class="v2-mobile-nav" aria-label="Mobile navigation">{#each mobileItems as item}<button aria-current={item.key===activeKey?'page':undefined} onclick={()=>onnavigate(item.key)}>{item.label}</button>{/each}</nav>
</div>
