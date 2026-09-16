<script lang="ts">
  import type { OrderedPolicyItem } from '../state/duplicatePolicyOrder';

  let {
    id,
    label,
    items,
    disabled = false,
    onchange,
  }: {
    id: string;
    label: string;
    items: OrderedPolicyItem[];
    disabled?: boolean;
    onchange: (ids: string[]) => void;
  } = $props();

  let draggedId = $state<string | null>(null);

  function move(itemId: string, offset: number): void {
    const index = items.findIndex((item) => item.id === itemId);
    const target = index + offset;
    if (index < 0 || target < 0 || target >= items.length) return;
    const next = items.map((item) => item.id);
    [next[index], next[target]] = [next[target], next[index]];
    onchange(next);
  }

  function drop(targetId: string): void {
    if (!draggedId || draggedId === targetId) return;
    const next = items.map((item) => item.id);
    const sourceIndex = next.indexOf(draggedId);
    const targetIndex = next.indexOf(targetId);
    if (sourceIndex < 0 || targetIndex < 0) return;
    const [moved] = next.splice(sourceIndex, 1);
    next.splice(targetIndex, 0, moved);
    draggedId = null;
    onchange(next);
  }
</script>

<fieldset {disabled} aria-describedby={`${id}-hint`}>
  <legend>{label}</legend>
  <p id={`${id}-hint`} class="hint">Highest priority first. Drag rows or use the move buttons.</p>
  <ol>
    {#each items as item, index (item.id)}
      <li
        class:unavailable={item.unavailable}
        draggable={!disabled}
        ondragstart={(event) => {
          draggedId = item.id;
          event.dataTransfer?.setData('text/plain', item.id);
        }}
        ondragend={() => draggedId = null}
        ondragover={(event) => event.preventDefault()}
        ondrop={(event) => {
          event.preventDefault();
          drop(item.id);
        }}
      >
        <span class="grip" aria-hidden="true">⋮⋮</span>
        <span class="copy">
          <strong>{item.label}</strong>
          <small>{item.description}</small>
        </span>
        {#if item.unavailable}<span class="badge">Unavailable</span>{/if}
        <span class="moves">
          <button type="button" disabled={disabled || index === 0} aria-label={`Move ${item.label} up`} onclick={() => move(item.id, -1)}>↑</button>
          <button type="button" disabled={disabled || index === items.length - 1} aria-label={`Move ${item.label} down`} onclick={() => move(item.id, 1)}>↓</button>
        </span>
      </li>
    {/each}
  </ol>
</fieldset>

<style>
  fieldset { display: grid; gap: .55rem; min-width: 0; margin: 0; padding: 0; border: 0; }
  legend { padding: 0; color: var(--color-ink-muted); font-size: .78rem; font-weight: 700; }
  .hint { margin: 0; color: var(--color-ink-muted); font-size: .72rem; }
  ol { display: grid; gap: .35rem; margin: 0; padding: 0; list-style: none; counter-reset: priority; }
  li { counter-increment: priority; display: grid; grid-template-columns: auto minmax(0, 1fr) auto auto; align-items: center; gap: .6rem; padding: .55rem .65rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); background: var(--color-canvas); }
  li::before { content: counter(priority); color: var(--color-ink-muted); font-size: .72rem; font-variant-numeric: tabular-nums; }
  li[draggable="true"] { cursor: grab; }
  li.unavailable { border-color: var(--color-danger, #b42318); }
  .grip { color: var(--color-ink-muted); letter-spacing: -.2em; }
  .copy { display: grid; min-width: 0; gap: .1rem; }
  strong { overflow: hidden; color: var(--color-ink-strong); font-size: .8rem; text-overflow: ellipsis; white-space: nowrap; }
  small { color: var(--color-ink-muted); font-size: .68rem; }
  .badge { padding: .18rem .35rem; border-radius: 999px; color: var(--color-danger, #b42318); background: color-mix(in srgb, var(--color-danger, #b42318) 10%, transparent); font-size: .62rem; font-weight: 800; text-transform: uppercase; }
  .moves { display: flex; gap: .2rem; }
  button { width: 1.8rem; height: 1.8rem; border: 1px solid var(--color-border-subtle); border-radius: var(--radius-sm); color: var(--color-ink-muted); background: var(--color-surface-soft); cursor: pointer; }
  button:disabled { opacity: .35; cursor: default; }
</style>
