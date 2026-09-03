<script lang="ts">
  import { onMount } from 'svelte';

  import { loadStatus } from '../features/status/api/statusApi';
  import type { StatusLoadState } from '../features/status/types/status';
  import demoHtml from './demo.html?raw';

  let frame: HTMLIFrameElement | undefined;
  let statusState: StatusLoadState = { kind: 'loading' };

  const statusBridge = String.raw`
<script>
(function () {
  let liveStatus = { kind: 'loading' };
  const demoRenderPage = window.renderPage;

  function escapeHtml(value) {
    return String(value == null ? '' : value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function badge(label, tone) {
    return '<span class="badge ' + tone + '">' + escapeHtml(label) + '</span>';
  }

  function dependencyLabel(dependency, readyLabel, unavailableLabel) {
    if (!dependency || !dependency.configured) return ['Not configured', 'warn'];
    if (dependency.status === 'ok') return [readyLabel, 'ok'];
    return [unavailableLabel, 'bad'];
  }

  function serverVersion(snapshot) {
    const version = snapshot.capabilities && snapshot.capabilities.immich_server && snapshot.capabilities.immich_server.server_version;
    if (!version) return 'Unknown';
    const prerelease = version.prerelease == null ? '' : '-' + version.prerelease;
    return version.major + '.' + version.minor + '.' + version.patch + prerelease;
  }

  function renderStatusLoading() {
    document.querySelector('.context').innerHTML = '<span class="zone">Context rail</span><div class="section" style="margin-top:14px"><div class="card muted">Loading environment status…</div></div>';
    document.querySelector('.content').innerHTML = '<div class="notice">Loading live Companion status…</div><div class="metric-grid"><div class="card metric"><b>…</b><span>Companion backend</span></div><div class="card metric"><b>…</b><span>Immich dependency</span></div><div class="card metric"><b>…</b><span>Capabilities</span></div><div class="card metric"><b>…</b><span>Immich version</span></div></div>';
    document.querySelector('.inspector').innerHTML = '<span class="zone">Inspector</span><div class="section" style="margin-top:14px"><div class="card small muted">Loading capabilities…</div></div>';
  }

  function renderStatusError(message) {
    document.querySelector('.context').innerHTML = '<span class="zone">Context rail</span><div class="section" style="margin-top:14px"><div class="card">' + badge('Unavailable', 'bad') + '<p class="muted small">Live status could not be loaded.</p></div></div>';
    document.querySelector('.content').innerHTML = '<div class="notice"><b>Status unavailable.</b><br>' + escapeHtml(message) + '<div style="margin-top:10px"><button class="primary" id="v2StatusRetry">Retry</button></div></div>';
    document.querySelector('.inspector').innerHTML = '<span class="zone">Inspector</span><div class="section" style="margin-top:14px"><div class="card small muted">No live capability data is available while the status request is failing.</div></div>';
    document.getElementById('v2StatusRetry')?.addEventListener('click', function () {
      liveStatus = { kind: 'loading' };
      renderStatusLoading();
      parent.postMessage({ type: 'immich-companion-v2-status-refresh' }, '*');
    });
  }

  function renderLiveStatus(snapshot) {
    const health = snapshot.health;
    const capabilities = snapshot.capabilities;
    const version = snapshot.version;
    const immich = dependencyLabel(health.dependencies.immich, 'Connected', 'Unavailable');
    const database = dependencyLabel(health.dependencies.companion_database, 'Ready', 'Unavailable');
    const companionTone = health.ready ? 'ok' : 'warn';
    const companionLabel = health.ready ? 'Healthy' : 'Degraded';
    const implemented = Array.isArray(capabilities.implemented) ? capabilities.implemented : [];
    const immichVersion = serverVersion(snapshot);

    document.querySelector('.context').innerHTML =
      '<span class="zone">Context rail</span>' +
      '<div class="section" style="margin-top:14px"><div class="section-title"><h3>Environment</h3></div><div class="card stack">' +
      '<div class="row" style="justify-content:space-between"><span>Companion</span>' + badge(companionLabel, companionTone) + '</div>' +
      '<div class="row" style="justify-content:space-between"><span>Immich API</span>' + badge(immich[0], immich[1]) + '</div>' +
      '<div class="row" style="justify-content:space-between"><span>Database</span>' + badge(database[0], database[1]) + '</div>' +
      '</div></div>' +
      '<div class="section"><div class="card small muted">Environment: ' + escapeHtml(version.environment) + '<br>Safe mode: ' + (health.safe_mode ? 'On' : 'Off') + '</div></div>';

    document.querySelector('.content').innerHTML =
      '<div class="row" style="justify-content:space-between;margin-bottom:12px"><div><span class="zone">Primary content</span> <b>System overview</b></div><button id="v2StatusRefresh">Refresh view</button></div>' +
      '<div class="metric-grid">' +
      '<div class="card metric"><b>' + escapeHtml(companionLabel) + '</b><span>Companion backend</span></div>' +
      '<div class="card metric"><b>' + escapeHtml(immich[0]) + '</b><span>Immich dependency</span></div>' +
      '<div class="card metric"><b>' + implemented.length + '</b><span>Capabilities</span></div>' +
      '<div class="card metric"><b>' + escapeHtml(immichVersion) + '</b><span>Immich version</span></div>' +
      '</div>' +
      '<div class="section" style="margin-top:14px"><div class="section-title"><h3>Dependencies</h3></div><div class="card"><table class="table">' +
      '<tr><th>Service</th><th>Status</th><th>Version</th><th>Details</th></tr>' +
      '<tr><td>Immich API</td><td>' + badge(immich[0], immich[1]) + '</td><td>' + escapeHtml(immichVersion) + '</td><td>' + escapeHtml(health.dependencies.immich.detail || 'Configured') + '</td></tr>' +
      '<tr><td>Companion API</td><td>' + badge(companionLabel, companionTone) + '</td><td>' + escapeHtml(version.version) + '</td><td>' + escapeHtml(health.status) + '</td></tr>' +
      '<tr><td>Database</td><td>' + badge(database[0], database[1]) + '</td><td>—</td><td>' + escapeHtml(health.dependencies.companion_database.detail || (health.dependencies.companion_database.configured ? 'Configured' : 'Not configured')) + '</td></tr>' +
      '</table></div></div>';

    document.querySelector('.inspector').innerHTML =
      '<span class="zone">Inspector</span><div class="section" style="margin-top:14px"><div class="section-title"><h3>Capabilities</h3></div><div class="card stack small">' +
      (implemented.length ? implemented.map(function (item) { return '<span>' + escapeHtml(item.replaceAll('_', ' ')) + '</span>'; }).join('') : '<span class="muted">No implemented capabilities reported.</span>') +
      '</div></div>' +
      '<div class="section"><div class="card small"><div class="row" style="justify-content:space-between"><span>Destructive actions</span>' + badge(capabilities.destructive_actions ? 'Enabled' : 'Disabled', capabilities.destructive_actions ? 'warn' : 'ok') + '</div></div></div>';

    document.getElementById('v2StatusRefresh')?.addEventListener('click', function () {
      liveStatus = { kind: 'loading' };
      renderStatusLoading();
      parent.postMessage({ type: 'immich-companion-v2-status-refresh' }, '*');
    });
  }

  function renderCurrentStatus() {
    if (liveStatus.kind === 'loading') renderStatusLoading();
    else if (liveStatus.kind === 'error') renderStatusError(liveStatus.message);
    else renderLiveStatus(liveStatus.snapshot);
  }

  window.renderPage = function (key) {
    demoRenderPage(key);
    if ((key || 'status') === 'status') renderCurrentStatus();
  };

  window.addEventListener('message', function (event) {
    if (event.source !== parent || !event.data || event.data.type !== 'immich-companion-v2-status') return;
    liveStatus = event.data.state;
    if ((location.hash || '#status').slice(1) === 'status') renderCurrentStatus();
  });

  window.renderPage((location.hash || '#status').slice(1));
  parent.postMessage({ type: 'immich-companion-v2-status-ready' }, '*');
})();
</script>`;

  const enhancedDemoHtml = demoHtml.replace('</body>', `${statusBridge}\n</body>`);

  function syncStatusToFrame(): void {
    frame?.contentWindow?.postMessage(
      { type: 'immich-companion-v2-status', state: statusState },
      '*',
    );
  }

  async function refreshStatus(): Promise<void> {
    statusState = { kind: 'loading' };
    syncStatusToFrame();

    try {
      const snapshot = await loadStatus();
      statusState = { kind: 'loaded', snapshot };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'An unknown status error occurred.';
      statusState = { kind: 'error', message };
    }

    syncStatusToFrame();
  }

  onMount(() => {
    const handleMessage = (event: MessageEvent): void => {
      if (event.source !== frame?.contentWindow || !event.data) return;

      if (event.data.type === 'immich-companion-v2-status-ready') {
        syncStatusToFrame();
      } else if (event.data.type === 'immich-companion-v2-status-refresh') {
        void refreshStatus();
      }
    };

    window.addEventListener('message', handleMessage);
    void refreshStatus();

    return () => window.removeEventListener('message', handleMessage);
  });
</script>

<svelte:head>
  <title>Immich Companion V2</title>
</svelte:head>

<iframe
  bind:this={frame}
  class="v2-demo"
  title="Immich Companion V2 demo shell"
  srcdoc={enhancedDemoHtml}
  onload={syncStatusToFrame}
></iframe>

<style>
  .v2-demo {
    display: block;
    width: 100vw;
    height: 100vh;
    border: 0;
    background: #0b1016;
  }
</style>
