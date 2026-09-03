<script lang="ts">
  import { onMount } from 'svelte';

  import { loadStatus } from '../../features/status/api/statusApi';
  import type { StatusLoadState, StatusSnapshot } from '../../features/status/types/status';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Ui from '../components/V2Ui.svelte';

  let loadState = $state<StatusLoadState>({ kind: 'loading' });
  let active = true;

  async function refresh(): Promise<void> {
    loadState = { kind: 'loading' };
    try {
      const snapshot = await loadStatus();
      if (active) loadState = { kind: 'loaded', snapshot };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'An unknown status error occurred.';
      if (active) loadState = { kind: 'error', message };
    }
  }

  function dependency(snapshot: StatusSnapshot, key: 'immich' | 'companion_database') {
    return snapshot.health.dependencies[key];
  }

  function dependencyState(status: string, configured: boolean, okLabel: string) {
    if (!configured) return { label: 'Not configured', tone: 'warn' as const };
    if (status === 'ok') return { label: okLabel, tone: 'ok' as const };
    return { label: 'Unavailable', tone: 'bad' as const };
  }

  function immichVersion(snapshot: StatusSnapshot): string {
    const version = snapshot.capabilities.immich_server?.server_version;
    if (!version) return 'Unknown';
    return `${version.major}.${version.minor}.${version.patch}${version.prerelease == null ? '' : `-${version.prerelease}`}`;
  }

  onMount(() => {
    active = true;
    void refresh();
    return () => { active = false; };
  });
</script>

<V2PageLayout
  title="Status"
  description="Read-only health, dependency, capability and version overview for Companion and its Immich connection."
>
  {#snippet context()}
    <span class="v2-zone">Context rail</span>
    {#if loadState.kind === 'loaded'}
      {@const snapshot = loadState.snapshot}
      {@const immich = dependencyState(dependency(snapshot, 'immich').status, dependency(snapshot, 'immich').configured, 'Connected')}
      {@const database = dependencyState(dependency(snapshot, 'companion_database').status, dependency(snapshot, 'companion_database').configured, 'Ready')}
      <V2Ui kind="section" title="Environment">
        <div class="v2-card v2-stack">
          <div class="v2-row v2-between"><span>Companion</span><V2Ui kind="badge" tone={snapshot.health.ready ? 'ok' : 'warn'} value={snapshot.health.ready ? 'Healthy' : 'Degraded'} /></div>
          <div class="v2-row v2-between"><span>Immich API</span><V2Ui kind="badge" tone={immich.tone} value={immich.label} /></div>
          <div class="v2-row v2-between"><span>Database</span><V2Ui kind="badge" tone={database.tone} value={database.label} /></div>
        </div>
      </V2Ui>
      <V2Ui kind="card"><div class="v2-small v2-muted">Environment: {snapshot.version.environment}<br>Safe mode: {snapshot.health.safe_mode ? 'On' : 'Off'}</div></V2Ui>
    {:else}
      <V2Ui kind="card"><div class="v2-small v2-muted">{loadState.kind === 'loading' ? 'Loading environment status…' : 'Live status unavailable.'}</div></V2Ui>
    {/if}
  {/snippet}

  {#snippet content()}
    {#if loadState.kind === 'loading'}
      <V2Ui kind="notice">Loading live Companion status…</V2Ui>
      <div class="v2-metric-grid">
        <V2Ui kind="metric" value="…" title="Companion backend" />
        <V2Ui kind="metric" value="…" title="Immich dependency" />
        <V2Ui kind="metric" value="…" title="Capabilities" />
        <V2Ui kind="metric" value="…" title="Immich version" />
      </div>
    {:else if loadState.kind === 'error'}
      <V2Ui kind="notice"><b>Status unavailable.</b><br>{loadState.message}<div style="margin-top:10px"><button class="v2-button v2-button-primary" onclick={refresh}>Retry</button></div></V2Ui>
    {:else}
      {@const snapshot = loadState.snapshot}
      {@const immichDep = dependency(snapshot, 'immich')}
      {@const databaseDep = dependency(snapshot, 'companion_database')}
      {@const immich = dependencyState(immichDep.status, immichDep.configured, 'Connected')}
      {@const database = dependencyState(databaseDep.status, databaseDep.configured, 'Ready')}
      <div class="v2-row v2-between" style="margin-bottom:12px">
        <div><span class="v2-zone">Primary content</span> <b>System overview</b></div>
        <button class="v2-button" onclick={refresh}>Refresh view</button>
      </div>
      <div class="v2-metric-grid">
        <V2Ui kind="metric" value={snapshot.health.ready ? 'Healthy' : 'Degraded'} title="Companion backend" />
        <V2Ui kind="metric" value={immich.label} title="Immich dependency" />
        <V2Ui kind="metric" value={String(snapshot.capabilities.implemented.length)} title="Capabilities" />
        <V2Ui kind="metric" value={immichVersion(snapshot)} title="Immich version" />
      </div>
      <V2Ui kind="section" title="Dependencies">
        <div class="v2-card">
          <table class="v2-table">
            <thead><tr><th>Service</th><th>Status</th><th>Version</th><th>Details</th></tr></thead>
            <tbody>
              <tr><td>Immich API</td><td><V2Ui kind="badge" tone={immich.tone} value={immich.label} /></td><td>{immichVersion(snapshot)}</td><td>{immichDep.detail ?? (immichDep.configured ? 'Configured' : 'Not configured')}</td></tr>
              <tr><td>Companion API</td><td><V2Ui kind="badge" tone={snapshot.health.ready ? 'ok' : 'warn'} value={snapshot.health.ready ? 'Healthy' : 'Degraded'} /></td><td>{snapshot.version.version}</td><td>{snapshot.health.status}</td></tr>
              <tr><td>Database</td><td><V2Ui kind="badge" tone={database.tone} value={database.label} /></td><td>—</td><td>{databaseDep.detail ?? (databaseDep.configured ? 'Configured' : 'Not configured')}</td></tr>
            </tbody>
          </table>
        </div>
      </V2Ui>
    {/if}
  {/snippet}

  {#snippet inspector()}
    <span class="v2-zone">Inspector</span>
    {#if loadState.kind === 'loaded'}
      <V2Ui kind="section" title="Capabilities">
        <div class="v2-card v2-stack v2-small">
          {#each loadState.snapshot.capabilities.implemented as capability}
            <span>{capability.replaceAll('_', ' ')}</span>
          {/each}
        </div>
      </V2Ui>
      <V2Ui kind="card">
        <div class="v2-row v2-between v2-small"><span>Destructive actions</span><V2Ui kind="badge" tone={loadState.snapshot.capabilities.destructive_actions ? 'warn' : 'ok'} value={loadState.snapshot.capabilities.destructive_actions ? 'Enabled' : 'Disabled'} /></div>
      </V2Ui>
    {:else}
      <V2Ui kind="card"><div class="v2-small v2-muted">{loadState.kind === 'loading' ? 'Loading capabilities…' : 'No live capability data available.'}</div></V2Ui>
    {/if}
  {/snippet}
</V2PageLayout>
