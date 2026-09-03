<script lang="ts">
  import { onMount } from 'svelte';
  import {
    readV2Density,
    V2_DENSITY_EVENT,
    writeV2Density,
    type V2Density,
  } from '../state/density';

  export type NavItem = {
    key: string;
    label: string;
    group?: string;
    position?: 'top' | 'bottom';
  };

  let {
    activeKey,
    title,
    navItems,
    onnavigate,
    brand = 'Immich Companion',
    connectionLabel = 'Immich connected v2.x',
    children,
  }: {
    activeKey: string;
    title: string;
    navItems: NavItem[];
    onnavigate: (key: string) => void;
    brand?: string;
    connectionLabel?: string;
    children: import('svelte').Snippet;
  } = $props();

  let density = $state<V2Density>('standard');
  let taskVisible = $state(true);

  function groupItems(items: NavItem[]) {
    const groups: { label: string; items: NavItem[] }[] = [];
    for (const item of items) {
      const label = item.group ?? '';
      let group = groups.find((entry) => entry.label === label);
      if (!group) {
        group = { label, items: [] };
        groups.push(group);
      }
      group.items.push(item);
    }
    return groups;
  }

  const topGroups = $derived(groupItems(navItems.filter((item) => item.position !== 'bottom')));
  const bottomGroups = $derived(groupItems(navItems.filter((item) => item.position === 'bottom')));

  function setDensity(next: V2Density): void {
    density = next;
    writeV2Density(next);
  }

  onMount(() => {
    density = readV2Density();
    const onDensity = (event: Event) => {
      density = (event as CustomEvent<V2Density>).detail;
    };
    window.addEventListener(V2_DENSITY_EVENT, onDensity);
    return () => window.removeEventListener(V2_DENSITY_EVENT, onDensity);
  });
</script>

<div class="v2-root" class:v2-condensed={density === 'condensed'}>
  <div class="v2-app">
    <aside class="v2-sidebar">
      <div class="v2-brand"><div class="v2-logo"></div><span class="v2-brand-text">{brand}</span></div>
      {#each topGroups as group}
        {#if group.label}<div class="v2-nav-label">{group.label}</div>{/if}
        <nav class="v2-nav" aria-label={group.label || 'Navigation'}>
          {#each group.items as item}
            <button class="v2-nav-button" class:active={item.key === activeKey} aria-current={item.key === activeKey ? 'page' : undefined} onclick={() => onnavigate(item.key)}>
              <i class="v2-nav-icon" aria-hidden="true"></i><span class="v2-nav-text">{item.label}</span>
            </button>
          {/each}
        </nav>
      {/each}
      <div class="v2-grow"></div>
      {#each bottomGroups as group}
        <nav class="v2-nav" aria-label={group.label || 'Secondary navigation'}>
          {#each group.items as item}
            <button class="v2-nav-button" class:active={item.key === activeKey} aria-current={item.key === activeKey ? 'page' : undefined} onclick={() => onnavigate(item.key)}>
              <i class="v2-nav-icon" aria-hidden="true"></i><span class="v2-nav-text">{item.label}</span>
            </button>
          {/each}
        </nav>
      {/each}
      <div class="v2-connection"><span class="v2-dot"></span>{connectionLabel}</div>
    </aside>

    <div class="v2-shell">
      <header class="v2-topbar">
        <div class="v2-crumb">{brand} / V2 / <span class="v2-crumb-current">{title}</span></div>
        <div class="v2-top-actions">
          <input class="v2-top-search" placeholder="Search current interface…" aria-label="Search current interface">
          <div class="v2-segmented" title="Interface density">
            <button class:active={density === 'standard'} onclick={() => setDensity('standard')}>Standard</button>
            <button class:active={density === 'condensed'} onclick={() => setDensity('condensed')}>Condensed</button>
          </div>
          <button class="v2-button" onclick={() => taskVisible = !taskVisible}>Tasks</button>
          <button class="v2-button" aria-label="More actions">⋯</button>
        </div>
      </header>
      {@render children()}
    </div>
  </div>

  {#if taskVisible}
    <div class="v2-tasktray">
      <div class="v2-inline v2-inline-sm v2-inline-align-center"><span class="v2-zone">Task tray</span><div><b>Background tasks</b><div class="v2-small v2-muted">No blocking task · global task feedback lives here</div></div></div>
      <div class="v2-inline v2-inline-sm v2-inline-align-center"><div class="v2-progress"><i></i></div><button class="v2-button" onclick={() => taskVisible = false}>Hide</button></div>
    </div>
  {/if}

  <nav class="v2-mobile-nav" aria-label="Mobile navigation">
    {#each ['status','assets','duplicates','albums','settings'] as key}<button onclick={() => onnavigate(key)}>{navItems.find((item) => item.key === key)?.label}</button>{/each}
  </nav>
</div>
