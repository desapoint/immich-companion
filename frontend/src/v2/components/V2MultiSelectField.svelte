<script lang="ts">
  import { Check, Search, X } from '@lucide/svelte';
  import { tick } from 'svelte';
  import { clickOutside } from '../../lib/actions/clickOutside';

  export type MultiSelectOption = {
    value: string;
    label: string;
    subtitle?: string;
    disabled?: boolean;
  };

  let {
    id,
    label = '',
    values = [],
    options,
    placeholder = 'Choose options',
    searchPlaceholder = 'Search options…',
    disabled = false,
    onvalueschange,
  }: {
    id: string;
    label?: string;
    values?: string[];
    options: MultiSelectOption[];
    placeholder?: string;
    searchPlaceholder?: string;
    disabled?: boolean;
    onvalueschange?: (values: string[]) => void;
  } = $props();

  let open = $state(false);
  let searchQuery = $state('');
  let trigger = $state<HTMLButtonElement>();
  let popup = $state<HTMLDivElement>();
  let searchInput = $state<HTMLInputElement>();
  let popupTop = $state(0);
  let popupLeft = $state(0);
  let popupWidth = $state(0);
  let popupMaxHeight = $state(360);

  const sortedOptions = $derived([...options].sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: 'base' })));
  const selectedSet = $derived(new Set(values));
  const selectedOptions = $derived(sortedOptions.filter((option) => selectedSet.has(option.value)));
  const normalizedSearch = $derived(searchQuery.trim().toLocaleLowerCase());
  const visibleOptions = $derived(!normalizedSearch
    ? sortedOptions
    : sortedOptions.filter((option) => `${option.label}\n${option.subtitle ?? ''}`.toLocaleLowerCase().includes(normalizedSearch)));
  const triggerText = $derived(selectedOptions.length === 0
    ? placeholder
    : selectedOptions.length === 1
      ? selectedOptions[0]?.label ?? placeholder
      : `${selectedOptions.length} selected`);

  function positionPopup(): void {
    if (!open || !trigger) return;
    const margin = 10;
    const gap = 5;
    const rect = trigger.getBoundingClientRect();
    const width = Math.min(520, Math.max(rect.width, 300, Math.min(window.innerWidth - margin * 2, 420)));
    const below = Math.max(0, window.innerHeight - rect.bottom - gap - margin);
    const above = Math.max(0, rect.top - gap - margin);
    const placeBelow = below >= 180 || below >= above;
    popupWidth = Math.min(width, window.innerWidth - margin * 2);
    popupLeft = Math.min(Math.max(rect.left, margin), window.innerWidth - popupWidth - margin);
    popupMaxHeight = Math.max(140, Math.min(360, placeBelow ? below : above));
    popupTop = placeBelow
      ? rect.bottom + gap
      : Math.max(margin, rect.top - gap - Math.min(popup?.scrollHeight ?? popupMaxHeight, popupMaxHeight));
  }

  function show(): void {
    if (disabled || sortedOptions.length === 0) return;
    searchQuery = '';
    open = true;
    void tick().then(() => {
      positionPopup();
      requestAnimationFrame(positionPopup);
      searchInput?.focus();
    });
  }

  function toggle(value: string): void {
    const next = new Set(values);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    onvalueschange?.([...next]);
  }

  function clear(event: MouseEvent): void {
    event.stopPropagation();
    if (disabled || values.length === 0) return;
    onvalueschange?.([]);
  }

  function handleSearchKey(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.preventDefault();
      open = false;
      searchQuery = '';
      void tick().then(() => trigger?.focus());
    } else if (event.key === 'ArrowDown') {
      event.preventDefault();
      popup?.querySelector<HTMLButtonElement>('.v2-multi-select-option:not(:disabled)')?.focus();
    }
  }

  function handleOptionKey(event: KeyboardEvent, option: MultiSelectOption): void {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      toggle(option.value);
    } else if (event.key === 'Escape') {
      event.preventDefault();
      open = false;
      void tick().then(() => trigger?.focus());
    }
  }

  $effect(() => {
    if (!open) return;
    const reposition = () => positionPopup();
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
    return () => {
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
    };
  });
</script>

<div class="v2-multi-select-field" use:clickOutside={{ enabled: open, onoutside: () => (open = false) }}>
  {#if label}<label class="v2-field-label" for={id}>{label}</label>{/if}
  <div class="v2-multi-select-control">
    <button
      bind:this={trigger}
      {id}
      type="button"
      class="v2-select-trigger v2-multi-select-trigger"
      data-placeholder={values.length === 0 || undefined}
      {disabled}
      aria-haspopup="listbox"
      aria-expanded={open}
      aria-controls={`${id}-options`}
      onclick={() => open ? open = false : show()}
      onkeydown={(event) => {
        if (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown') {
          event.preventDefault();
          show();
        }
      }}
    >
      <span class="v2-select-trigger-copy"><span>{triggerText}</span></span>
      <span class="v2-select-chevron" aria-hidden="true"></span>
    </button>
    {#if values.length > 0}
      <button class="v2-multi-select-clear" type="button" {disabled} aria-label={`Clear ${label || 'selections'}`} onclick={clear}><X size={15}/></button>
    {/if}
  </div>

  {#if open}
    <div
      bind:this={popup}
      id={`${id}-options`}
      class="v2-multi-select-popup"
      role="listbox"
      aria-multiselectable="true"
      style={`top:${popupTop}px;left:${popupLeft}px;width:${popupWidth}px;max-height:${popupMaxHeight}px`}
    >
      <div class="v2-multi-select-search">
        <Search size={15} aria-hidden="true"/>
        <input bind:this={searchInput} type="search" bind:value={searchQuery} placeholder={searchPlaceholder} onkeydown={handleSearchKey}/>
      </div>
      <div class="v2-multi-select-list">
        {#if visibleOptions.length === 0}
          <div class="v2-multi-select-empty">No matches</div>
        {:else}
          {#each visibleOptions as option (option.value)}
            <button
              type="button"
              class="v2-multi-select-option"
              role="option"
              aria-selected={selectedSet.has(option.value)}
              disabled={option.disabled}
              onclick={() => toggle(option.value)}
              onkeydown={(event) => handleOptionKey(event, option)}
            >
              <span class="v2-multi-select-check" data-selected={selectedSet.has(option.value) || undefined}>{#if selectedSet.has(option.value)}<Check size={14}/>{/if}</span>
              <span class="v2-multi-select-copy"><span>{option.label}</span>{#if option.subtitle}<small>{option.subtitle}</small>{/if}</span>
            </button>
          {/each}
        {/if}
      </div>
    </div>
  {/if}
</div>

<style>
  .v2-multi-select-field { display:grid; gap:.35rem; min-width:0; }
  .v2-multi-select-control { position:relative; min-width:0; }
  .v2-multi-select-trigger { width:100%; text-align:left; }
  .v2-multi-select-clear { position:absolute; z-index:1; top:50%; right:2.15rem; display:grid; width:1.8rem; height:1.8rem; place-items:center; transform:translateY(-50%); border:0; border-radius:999px; color:inherit; background:transparent; cursor:pointer; opacity:.65; }
  .v2-multi-select-clear:hover:not(:disabled) { background:color-mix(in srgb,currentColor 9%,transparent); opacity:1; }
  .v2-multi-select-popup { position:fixed; z-index:1000; display:grid; grid-template-rows:auto minmax(0,1fr); overflow:hidden; border:1px solid var(--v2-border,rgba(127,127,127,.32)); border-radius:.65rem; background:var(--v2-surface,Canvas); box-shadow:0 .7rem 2rem rgba(0,0,0,.2); }
  .v2-multi-select-search { display:grid; grid-template-columns:auto minmax(0,1fr); align-items:center; gap:.5rem; padding:.5rem; border-bottom:1px solid var(--v2-border,rgba(127,127,127,.25)); }
  .v2-multi-select-search input { width:100%; min-width:0; border:0; outline:0; background:transparent; color:inherit; font:inherit; }
  .v2-multi-select-list { overflow:auto; padding:.35rem; }
  .v2-multi-select-option { width:100%; display:grid; grid-template-columns:auto minmax(0,1fr); align-items:center; gap:.6rem; padding:.55rem .6rem; border:0; border-radius:.45rem; color:inherit; background:transparent; text-align:left; font:inherit; cursor:pointer; }
  .v2-multi-select-option:hover:not(:disabled), .v2-multi-select-option:focus-visible { background:color-mix(in srgb,currentColor 8%,transparent); outline:none; }
  .v2-multi-select-option:disabled { opacity:.42; cursor:not-allowed; }
  .v2-multi-select-check { display:grid; width:1.15rem; height:1.15rem; place-items:center; border:1px solid var(--v2-border,rgba(127,127,127,.45)); border-radius:.3rem; }
  .v2-multi-select-check[data-selected] { border-color:var(--v2-accent,currentColor); background:color-mix(in srgb,var(--v2-accent,currentColor) 18%,transparent); }
  .v2-multi-select-copy { display:grid; min-width:0; gap:.08rem; }
  .v2-multi-select-copy > span { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .v2-multi-select-copy small { color:var(--v2-muted); font-size:.72rem; }
  .v2-multi-select-empty { padding:1rem; color:var(--v2-muted); text-align:center; }
</style>
