<script lang="ts">
  import V2Shell from './components/V2Shell.svelte';
  import V2PlaceholderPage from './pages/V2PlaceholderPage.svelte';
  import V2StatusPage from './pages/V2StatusPage.svelte';
  import './styles/v2.css';

  type PageKey = 'status' | 'assets' | 'restore' | 'duplicates' | 'albums' | 'tags' | 'settings' | 'docs';
  type NavItem = { key: PageKey; label: string; group?: string; position?: 'top' | 'bottom' };
  type PageConfig = {
    title: string;
    description: string;
    contextText: string;
    contentText: string;
    inspectorText: string;
  };

  const navItems: NavItem[] = [
    { key: 'status', label: 'Status', group: 'Library' },
    { key: 'assets', label: 'Assets', group: 'Library' },
    { key: 'restore', label: 'Restore', group: 'Library' },
    { key: 'duplicates', label: 'Duplicates', group: 'Library' },
    { key: 'albums', label: 'Albums', group: 'Organize' },
    { key: 'tags', label: 'Tags', group: 'Organize' },
    { key: 'settings', label: 'Settings', position: 'bottom' },
    { key: 'docs', label: 'API Docs', position: 'bottom' },
  ];

  const pageConfig: Record<Exclude<PageKey, 'status'>, PageConfig> = {
    assets: {
      title: 'Assets',
      description: 'Search, browse, select, synchronize and perform guarded actions on assets.',
      contextText: 'Simple / Expert search controls will be integrated later.',
      contentText: 'Demo Assets page content only. Controls are intentionally not connected yet.',
      inspectorText: 'Selection and action summaries remain placeholders.',
    },
    restore: {
      title: 'Restore',
      description: 'Review current Immich trash and restore individual, selected, or all trashed assets.',
      contextText: 'Trash summary and selection controls remain demo-only.',
      contentText: 'Demo Restore page content only.',
      inspectorText: 'Restore actions will be connected in a later V2 slice.',
    },
    duplicates: {
      title: 'Duplicates',
      description: 'Review exact and similarity duplicate groups, save member decisions, and process only actionable groups.',
      contextText: 'Review filters, similarity controls, and bulk presets remain static.',
      contentText: 'Demo duplicate content only. Comparison and decisions are not wired yet.',
      inspectorText: 'Batch readiness and current-group summaries remain placeholders.',
    },
    albums: {
      title: 'Albums',
      description: 'Search, sort, create, edit, delete and use albums to filter the Assets workspace.',
      contextText: 'Album search and sorting controls remain demo-only.',
      contentText: 'Demo Albums page content only.',
      inspectorText: 'Album editor remains a placeholder.',
    },
    tags: {
      title: 'Tags',
      description: 'Manage searchable hierarchical tags, parent relationships, colors and asset filters.',
      contextText: 'Tag tree and search controls remain demo-only.',
      contentText: 'Demo Tags page content only.',
      inspectorText: 'Tag editor remains a placeholder.',
    },
    settings: {
      title: 'Settings',
      description: 'Configure background load limits, duplicate defaults and incremental/global synchronization schedules.',
      contextText: 'Settings sections remain demo-only.',
      contentText: 'Demo Settings page content only.',
      inspectorText: 'Validation summaries remain placeholders.',
    },
    docs: {
      title: 'API Docs',
      description: 'Developer-facing API documentation inside the V2 shell.',
      contextText: 'API resource navigation remains demo-only.',
      contentText: 'Demo API Docs page content only.',
      inspectorText: 'Endpoint details remain placeholders.',
    },
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

<V2Shell
  {activeKey}
  title={activeKey === 'status' ? 'Status' : pageConfig[activeKey].title}
  {navItems}
  onnavigate={navigate}
>
  {#if activeKey === 'status'}
    <V2StatusPage />
  {:else}
    {@const page = pageConfig[activeKey]}
    <V2PlaceholderPage
      title={page.title}
      description={page.description}
      contextText={page.contextText}
      contentText={page.contentText}
      inspectorText={page.inspectorText}
    />
  {/if}
</V2Shell>
