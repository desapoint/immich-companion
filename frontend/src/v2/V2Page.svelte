<script lang="ts">
  import V2Shell from './components/V2Shell.svelte';
  import V2ImplementationWarning from './components/V2ImplementationWarning.svelte';
  import V2SettingsPage from './pages/V2SettingsPage.svelte';
  import './styles/index.css';

  type PageKey = 'status' | 'assets' | 'restore' | 'duplicates' | 'albums' | 'tags' | 'settings' | 'docs' | 'playground';
  type NavItem = { key: PageKey; label: string; group?: string; position?: 'top' | 'bottom' };

  const navItems: NavItem[] = [
    { key: 'status', label: 'Status', group: 'Library' },
    { key: 'assets', label: 'Assets', group: 'Library' },
    { key: 'restore', label: 'Restore', group: 'Library' },
    { key: 'duplicates', label: 'Duplicates', group: 'Library' },
    { key: 'albums', label: 'Albums', group: 'Organize' },
    { key: 'tags', label: 'Tags', group: 'Organize' },
    { key: 'settings', label: 'Settings', position: 'bottom' },
    { key: 'docs', label: 'API Docs', position: 'bottom' },
    { key: 'playground', label: 'Playground', position: 'bottom' },
  ];

  const titles: Record<PageKey, string> = {
    status: 'Status',
    assets: 'Assets',
    restore: 'Restore',
    duplicates: 'Duplicates',
    albums: 'Albums',
    tags: 'Tags',
    settings: 'Settings',
    docs: 'API Docs',
    playground: 'Playground',
  };

  function keyFromHash(): PageKey {
    const key = window.location.hash.slice(1) as PageKey;
    return navItems.some((item) => item.key === key) ? key : 'settings';
  }

  let activeKey = $state<PageKey>(keyFromHash());

  function navigate(key: string): void {
    activeKey = key as PageKey;
    history.replaceState(null, '', `#${key}`);
  }
</script>

<svelte:window onhashchange={() => (activeKey = keyFromHash())} />
<svelte:head><title>Immich Companion V2</title></svelte:head>

<V2Shell {activeKey} title={titles[activeKey]} {navItems} onnavigate={navigate}>
  {#if activeKey === 'settings'}
    <V2SettingsPage />
  {:else}
    <V2ImplementationWarning
      title={titles[activeKey]}
      description={`${titles[activeKey]} remains intentionally non-live in V2 while synchronization is implemented and validated. No backend action is available from this page yet.`}
    />
  {/if}
</V2Shell>
