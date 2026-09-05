<script lang="ts">
  import { Eye } from '@lucide/svelte';
  import V2RoundCheckbox from './V2RoundCheckbox.svelte';

  let {
    index,
    label,
    sublabel = '',
    selected = false,
    selectionMode = false,
    onactivate,
    onselect,
    onpreview,
    onpointerdown,
    image,
  }: {
    index: number;
    label: string;
    sublabel?: string;
    selected?: boolean;
    selectionMode?: boolean;
    onactivate?: (event: MouseEvent) => void;
    onselect?: (event: MouseEvent) => void;
    onpreview?: () => void;
    onpointerdown?: (event: PointerEvent) => void;
    image?: string;
  } = $props();

  const visualVariant = $derived(String(index % 3));
</script>

<div
  class="v2-asset-tile"
  class:selected
  class:selection-mode={selectionMode}
  data-variant={visualVariant}
  data-asset-id={index}
>
  <button
    class="v2-asset-main"
    type="button"
    aria-label={selectionMode ? `${selected ? 'Deselect' : 'Select'} ${label}` : `Preview ${label}`}
    aria-pressed={selectionMode ? selected : undefined}
    onclick={onactivate}
    onpointerdown={onpointerdown}
    ondragstart={(event) => event.preventDefault()}
  >
    {#if image}<img src={image} alt="">{/if}
    <span class="v2-asset-meta"><b>{label}</b>{#if sublabel}<small>{sublabel}</small>{/if}</span>
  </button>

  <span class="v2-asset-checkbox-zone">
    <V2RoundCheckbox
      checked={selected}
      ariaLabel={`${selected ? 'Deselect' : 'Select'} ${label}`}
      onclick={onselect}
    />
  </span>

  <button
    class="v2-asset-preview-zone"
    class:visible={selectionMode}
    type="button"
    aria-label={`Preview ${label}`}
    title="Preview"
    tabindex={selectionMode ? 0 : -1}
    disabled={!selectionMode}
    onclick={(event) => {
      event.stopPropagation();
      onpreview?.();
    }}
    onpointerdown={(event) => event.stopPropagation()}
  >
    <Eye size={17} aria-hidden="true" />
  </button>
</div>
