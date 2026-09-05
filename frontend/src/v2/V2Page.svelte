<script lang="ts">
  import V2Shell from './components/V2Shell.svelte';
  import V2StatusPage from './pages/V2StatusPage.svelte';
  import V2AssetsPage from './pages/V2AssetsPage.svelte';
  import V2RestorePage from './pages/V2RestorePage.svelte';
  import V2DuplicatesPage from './pages/V2DuplicatesPage.svelte';
  import V2AlbumsPage from './pages/V2AlbumsPage.svelte';
  import V2TagsPage from './pages/V2TagsPage.svelte';
  import V2SettingsPage from './pages/V2SettingsPage.svelte';
  import V2DocsPage from './pages/V2DocsPage.svelte';
  import V2PlaygroundPage from './pages/V2PlaygroundPage.svelte';
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
    return navItems.some((item) => item.key === key) ? key : 'status';
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
  {#if activeKey === 'status'}
    <V2StatusPage />
  {:else if activeKey === 'assets'}
    <V2AssetsPage />
  {:else if activeKey === 'restore'}
    <V2RestorePage />
  {:else if activeKey === 'duplicates'}
    <V2DuplicatesPage />
  {:else if activeKey === 'albums'}
    <V2AlbumsPage />
  {:else if activeKey === 'tags'}
    <V2TagsPage />
  {:else if activeKey === 'settings'}
    <V2SettingsPage />
  {:else if activeKey === 'docs'}
    <V2DocsPage />
  {:else}
    <V2PlaygroundPage />
  {/if}
</V2Shell>
