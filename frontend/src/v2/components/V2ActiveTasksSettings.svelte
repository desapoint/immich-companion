<script lang="ts">
  import { onMount } from 'svelte';
  import V2Badge from '../../lib/components/ui/Badge.svelte';
  import V2Button from '../../lib/components/ui/Button.svelte';
  import V2Card from '../../lib/components/ui/Card.svelte';
  import V2Notice from '../../lib/components/ui/Notice.svelte';
  import V2Stack from '../../lib/components/layout/Stack.svelte';
  import { libraryData } from '../../app/data/currentDataSource.svelte';
  import type { TaskRecord } from '../../features/status/types/syncContracts';

  const limit = 200;
  const activeStates = new Set(['queued', 'running', 'retrying', 'recovering', 'pause_requested', 'paused', 'cancel_requested']);
  let tasks = $state<TaskRecord[]>([]);
  let loading = $state(true);
  let refreshing = $state(false);
  let error = $state<string | null>(null);
  let notice = $state<string | null>(null);
  let cancellingIds = $state<string[]>([]);
  let mounted = false;
  let refreshController: AbortController | null = null;
  let taskRevision = 0;

  function label(value: string): string {
    return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function progress(task: TaskRecord): string | null {
    const detail = task.progress.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    const phase = task.progress.phase;
    return typeof phase === 'string' && phase.trim() ? label(phase) : null;
  }

  async function refresh(): Promise<void> {
    if (refreshController) return;
    const controller = new AbortController();
    refreshController = controller;
    refreshing = true;
    const revision = taskRevision;
    try {
      const current = await libraryData.tasks.listActive(limit, controller.signal);
      if (!mounted) return;
      if (revision === taskRevision) tasks = current;
      error = null;
    } catch (value) {
      if (mounted && !controller.signal.aborted) error = value instanceof Error ? value.message : 'Could not load active tasks.';
    } finally {
      if (mounted) loading = false;
      if (mounted) refreshing = false;
      refreshController = null;
    }
  }

  async function cancel(task: TaskRecord): Promise<void> {
    if (task.status === 'cancel_requested' || cancellingIds.includes(task.id)) return;
    cancellingIds = [...cancellingIds, task.id];
    error = null;
    notice = null;
    try {
      const updated = await libraryData.tasks.cancel(task.id);
      if (!mounted) return;
      taskRevision += 1;
      tasks = tasks.filter((item) => item.id !== task.id);
      if (activeStates.has(updated.status)) tasks = [updated, ...tasks];
      notice = updated.status === 'cancelled' ? 'Task cancelled.' : updated.status === 'cancel_requested' ? 'Cancellation requested. The worker will stop at its next cancellation checkpoint.' : 'The task already finished.';
    } catch (value) {
      if (mounted) error = value instanceof Error ? value.message : 'Could not cancel the task.';
    } finally {
      if (mounted) cancellingIds = cancellingIds.filter((id) => id !== task.id);
    }
  }

  onMount(() => {
    mounted = true;
    const subscription = libraryData.tasks.subscribe({
      onTask: (task) => {
        taskRevision += 1;
        tasks = tasks.filter((item) => item.id !== task.id);
        if (activeStates.has(task.status)) tasks = [task, ...tasks];
      },
      onConnectionState: () => undefined,
      onRecovered: () => void refresh(),
    });
    const interval = setInterval(() => void refresh(), 10_000);
    void refresh();
    return () => {
      mounted = false;
      refreshController?.abort();
      subscription.close();
      clearInterval(interval);
    };
  });
</script>

<V2Card title="Active tasks">
  {#snippet actions()}<V2Button disabled={refreshing} onclick={() => void refresh()}>Refresh</V2Button>{/snippet}
  <V2Stack gap="sm">
    <span class="v2-small v2-muted">Running, queued, retrying, and paused work appears here. Cancelling a running task requests a stop at its next checkpoint.</span>
    {#if error}<V2Notice tone="error" title="Task request failed">{error}</V2Notice>{/if}
    {#if notice}<V2Notice tone="info">{notice}</V2Notice>{/if}
    {#if loading}<V2Notice>Loading active tasks…</V2Notice>
    {:else if tasks.length === 0}<V2Notice tone="info">No active tasks.</V2Notice>
    {:else}
      <ul class="task-list">
        {#each tasks as task (task.id)}
          <li class="task-row">
            <div class="task-details">
              <div class="task-heading"><strong>{label(task.taskType)}</strong><V2Badge tone={task.status === 'cancel_requested' ? 'warn' : 'default'} text={label(task.status)} /></div>
              {#if progress(task)}<span class="v2-small">{progress(task)}</span>{/if}
              <span class="v2-small v2-muted">Attempt {task.attempt} · Started {task.startedAt ? new Date(task.startedAt).toLocaleString() : 'not yet'} · {task.id}</span>
            </div>
            <V2Button variant="danger" disabled={task.status === 'cancel_requested' || cancellingIds.includes(task.id)} onclick={() => void cancel(task)}>{cancellingIds.includes(task.id) ? 'Cancelling…' : task.status === 'cancel_requested' ? 'Cancellation requested' : 'Cancel'}</V2Button>
          </li>
        {/each}
      </ul>
      {#if tasks.length === limit}<span class="v2-small v2-muted">Showing the newest {limit} active tasks.</span>{/if}
    {/if}
  </V2Stack>
</V2Card>

<style>
  .task-list{list-style:none;margin:0;padding:0;display:grid;gap:.65rem}
  .task-row{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:.8rem;border:1px solid var(--v2-border,rgba(127,127,127,.22));border-radius:.65rem}
  .task-details{display:grid;gap:.3rem;min-width:0;overflow-wrap:anywhere}
  .task-heading{display:flex;align-items:center;flex-wrap:wrap;gap:.5rem}
  @media(max-width:640px){.task-row{align-items:flex-start;flex-direction:column}}
</style>
