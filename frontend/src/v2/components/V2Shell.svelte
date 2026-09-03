<script lang="ts">
  export type NavItem = { key: string; label: string; group?: string; position?: 'top' | 'bottom' };

  let {
    activeKey,
    title,
    navItems,
    onnavigate,
    brand = 'Immich Companion',
    connectionLabel = 'V2 workspace',
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
      <div class="v2-brand"><div class="v2-logo"></div><span class="v2-brand-text">{brand}</span></div>
      {#each topGroups as group}
        {#if group.label}<div class="v2-nav-label">{group.label}</div>{/if}
        <nav class="v2-nav" aria-label={group.label || 'Navigation'}>
          {#each group.items as item}
            <button
              class:active={item.key === activeKey}
              class="v2-nav-button"
              aria-current={item.key === activeKey ? 'page' : undefined}
              onclick={() => onnavigate(item.key)}
            ><i class="v2-nav-icon" aria-hidden="true"></i><span class="v2-nav-text">{item.label}</span></button>
          {/each}
        </nav>
      {/each}
      <div class="v2-grow"></div>
      {#each bottomGroups as group}
        {#if group.label}<div class="v2-nav-label">{group.label}</div>{/if}
        <nav class="v2-nav" aria-label={group.label || 'Secondary navigation'}>
          {#each group.items as item}
            <button
              class:active={item.key === activeKey}
              class="v2-nav-button"
              aria-current={item.key === activeKey ? 'page' : undefined}
              onclick={() => onnavigate(item.key)}
            ><i class="v2-nav-icon" aria-hidden="true"></i><span class="v2-nav-text">{item.label}</span></button>
          {/each}
        </nav>
      {/each}
      <div class="v2-connection"><span class="v2-dot"></span>{connectionLabel}</div>
    </aside>

    <div class="v2-shell">
      <header class="v2-topbar">
        <div class="v2-crumb">{brand} / V2 / <span class="v2-crumb-current">{title}</span></div>
        <div class="v2-top-actions">
          <input class="v2-top-search" placeholder="Search current interface…" disabled aria-label="Search current interface">
          <button class="v2-button" disabled>Tasks</button>
          <button class="v2-button" disabled aria-label="More actions">⋯</button>
        </div>
      </header>
      {@render children()}
    </div>
  </div>
</div>
