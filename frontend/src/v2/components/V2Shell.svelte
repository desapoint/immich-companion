<script lang="ts">
  export type NavItem = { key: string; label: string; group?: string; position?: 'top' | 'bottom' };

  let {
    activeKey,
    title,
    navItems,
    onnavigate,
    children,
  }: {
    activeKey: string;
    title: string;
    navItems: NavItem[];
    onnavigate: (key: string) => void;
    children: import('svelte').Snippet;
  } = $props();

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
</script>

<div class="v2-root">
  <div class="v2-app">
    <aside class="v2-sidebar">
      <div class="v2-brand"><div class="v2-logo"></div><span>Immich Companion</span></div>
      {#each topGroups as group}
        {#if group.label}<div class="v2-nav-label">{group.label}</div>{/if}
        <nav class="v2-nav">
          {#each group.items as item}
            <button class:active={item.key === activeKey} class="v2-nav-button" onclick={() => onnavigate(item.key)}><i class="v2-nav-icon"></i><span>{item.label}</span></button>
          {/each}
        </nav>
      {/each}
      <div class="v2-grow"></div>
      {#each bottomGroups as group}
        {#if group.label}<div class="v2-nav-label">{group.label}</div>{/if}
        <nav class="v2-nav">
          {#each group.items as item}
            <button class:active={item.key === activeKey} class="v2-nav-button" onclick={() => onnavigate(item.key)}><i class="v2-nav-icon"></i><span>{item.label}</span></button>
          {/each}
        </nav>
      {/each}
      <div class="v2-connection"><span class="v2-dot"></span>V2 workspace</div>
    </aside>

    <div class="v2-shell">
      <header class="v2-topbar">
        <div class="v2-crumb">Immich Companion / V2 / <b>{title}</b></div>
        <div class="v2-top-actions">
          <input class="v2-top-search" placeholder="Search current interface…" disabled>
          <button class="v2-button" disabled>Tasks</button>
          <button class="v2-button" disabled>⋯</button>
        </div>
      </header>
      {@render children()}
    </div>
  </div>
</div>
