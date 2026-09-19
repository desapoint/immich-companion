<script lang="ts">
  import { Keyboard } from '@lucide/svelte';
  import V2Button from './V2Button.svelte';

  export type KeyboardShortcut = {
    keys: string | string[];
    description: string;
  };

  let {
    shortcuts = [],
    title = 'Keyboard shortcuts',
  }: {
    shortcuts?: KeyboardShortcut[];
    title?: string;
  } = $props();

  let open = $state(false);
  let root = $state<HTMLElement | null>(null);

  function keyList(shortcut: KeyboardShortcut): string[] {
    return Array.isArray(shortcut.keys) ? shortcut.keys : [shortcut.keys];
  }

  function handleWindowPointer(event: PointerEvent): void {
    if (!open || !root || !(event.target instanceof Node)) return;
    if (!root.contains(event.target)) open = false;
  }
</script>

<svelte:window onpointerdown={handleWindowPointer} />

<div class="v2-keyboard-shortcuts" bind:this={root}>
  <V2Button
    iconOnly
    active={open}
    title={title}
    ariaLabel={title}
    onclick={() => (open = !open)}
  >
    <Keyboard size={17} aria-hidden="true" />
  </V2Button>

  {#if open}
    <div class="v2-keyboard-shortcuts-popover" role="dialog" aria-label={title}>
      <strong>{title}</strong>
      <div class="v2-keyboard-shortcuts-list">
        {#each shortcuts as shortcut}
          <div class="v2-keyboard-shortcuts-row">
            <span class="v2-keyboard-shortcuts-keys">
              {#each keyList(shortcut) as key}
                <kbd>{key}</kbd>
              {/each}
            </span>
            <span>{shortcut.description}</span>
          </div>
        {/each}
      </div>
    </div>
  {/if}
</div>

<style>
  .v2-keyboard-shortcuts { position:relative; flex:0 0 auto; }
  .v2-keyboard-shortcuts-popover {
    position:absolute;
    z-index:220;
    top:calc(100% + 7px);
    right:0;
    width:max-content;
    min-width:260px;
    max-width:min(360px,calc(100vw - 24px));
    display:flex;
    flex-direction:column;
    gap:10px;
    border:1px solid var(--v2-line);
    border-radius:10px;
    background:var(--v2-surface-2);
    box-shadow:0 16px 36px rgba(0,0,0,.38);
    padding:12px;
    color:var(--v2-text);
  }
  .v2-keyboard-shortcuts-popover>strong { font-size:12px; }
  .v2-keyboard-shortcuts-list { display:grid; gap:7px; }
  .v2-keyboard-shortcuts-row {
    display:grid;
    grid-template-columns:minmax(84px,auto) minmax(0,1fr);
    gap:12px;
    align-items:center;
    font-size:12px;
    color:#c4cfda;
  }
  .v2-keyboard-shortcuts-keys { display:flex; align-items:center; gap:4px; flex-wrap:wrap; }
  kbd {
    min-width:25px;
    min-height:23px;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    border:1px solid #46566c;
    border-bottom-color:#2c3747;
    border-radius:6px;
    background:#0b1118;
    color:#dce7f5;
    padding:2px 6px;
    font:600 11px/1 system-ui,sans-serif;
    box-shadow:0 1px 0 #000;
  }
</style>
