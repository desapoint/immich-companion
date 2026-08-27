<script lang="ts">
  import type { AssetTaskStatus } from '../types/assets';

  interface Props {
    tasks: AssetTaskStatus[];
  }

  let { tasks }: Props = $props();
  const label = (task: AssetTaskStatus): string => {
    const completed = task.result?.summary?.applied_count ?? task.counters.processed ?? 0;
    const requested = task.counters.requested ?? 0;
    return `${task.status.replace('_', ' ')} · ${completed.toLocaleString()}/${requested.toLocaleString()} assets`;
  };
</script>

{#if tasks.length}
  <section class="history" aria-labelledby="action-history-title">
    <h2 id="action-history-title">Recent actions</h2>
    <ul>
      {#each tasks as task (task.id)}
        <li><span>{label(task)}</span><time datetime={task.created_at}>{new Date(task.created_at).toLocaleString()}</time></li>
      {/each}
    </ul>
  </section>
{/if}

<style>
  .history { display: grid; gap: 0.5rem; padding: 0.8rem 1rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-md); background: var(--color-surface-raised); }
  h2 { margin: 0; font-size: 0.8rem; }
  ul { display: grid; gap: 0.35rem; margin: 0; padding: 0; list-style: none; }
  li { display: flex; justify-content: space-between; gap: 1rem; color: var(--color-ink-muted); font-size: 0.7rem; }
  time { white-space: nowrap; }
</style>
