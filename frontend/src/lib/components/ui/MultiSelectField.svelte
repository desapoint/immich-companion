<script lang="ts">
  import { tick } from 'svelte';

  import { clickOutside } from '../../actions/clickOutside';
  import type { SelectOption } from '../../types/ui';
  import {
    floatingPopoverLayout,
    type FloatingPopoverLayout,
  } from '../../utils/floatingPopover';
  import MultiSelectSummary from './MultiSelectSummary.svelte';
  import MultiSelectPopover from './MultiSelectPopover.svelte';
  import {
    canCreateSelectOption,
    filterSelectOptions,
    firstEnabledOptionIndex,
    nextEnabledOptionIndex,
  } from './multiSelectOptions';

  interface Props {
    id: string;
    label: string;
    values: string[];
    options: SelectOption[];
    placeholder?: string;
    disabled?: boolean;
    required?: boolean;
    compact?: boolean;
    searchable?: boolean;
    allowCreate?: boolean;
    createLabel?: string;
    oncreate?: (value: string) => void;
    onchange: (values: string[]) => void;
  }

  let {
    id,
    label,
    values,
    options,
    placeholder = 'Any value',
    disabled = false,
    required = false,
    compact = false,
    searchable = false,
    allowCreate = false,
    createLabel = 'Add',
    oncreate,
    onchange,
  }: Props = $props();

  let triggerElement = $state<HTMLButtonElement>();
  let searchElement = $state<HTMLInputElement>();
  let listElement = $state<HTMLDivElement>();
  let open = $state(false);
  let query = $state('');
  let activeIndex = $state(0);
  let popoverLayout = $state<FloatingPopoverLayout | null>(null);

  const selectedOptions = $derived(
    values
      .map((value) => options.find((option) => option.value === value))
      .filter((option): option is SelectOption => Boolean(option)),
  );
  const filteredOptions = $derived(filterSelectOptions(options, query, searchable));
  const canCreate = $derived(canCreateSelectOption(options, query, allowCreate));

  function firstEnabledIndex(): number {
    return firstEnabledOptionIndex(filteredOptions);
  }

  function adjacentEnabledIndex(start: number, direction: 1 | -1): number {
    return nextEnabledOptionIndex(filteredOptions, start, direction);
  }


  async function focusOption(index = activeIndex): Promise<void> {
    await tick();
    listElement?.querySelector<HTMLButtonElement>(`[data-option-index="${index}"]`)?.focus();
  }

  async function openList(focusOptions = false): Promise<void> {
    if (disabled) return;
    query = '';
    activeIndex = Math.max(0, firstEnabledIndex());
    open = true;
    await tick();
    updatePopoverLayout();
    await tick();
    if (searchable && !focusOptions) searchElement?.focus();
    else if (options.length) await focusOption();
  }

  async function closeList(restoreFocus = false): Promise<void> {
    open = false;
    query = '';
    if (restoreFocus) {
      await tick();
      triggerElement?.focus();
    }
  }

  function toggle(option: SelectOption): void {
    if (disabled || option.disabled) return;
    const next = values.includes(option.value)
      ? values.filter((value) => value !== option.value)
      : [...values, option.value];
    onchange(next);
  }

  function updatePopoverLayout(): void {
    if (!open || !triggerElement) return;
    popoverLayout = floatingPopoverLayout(
      triggerElement.getBoundingClientRect(),
      window.innerWidth,
      window.innerHeight,
    );
  }

  function handleTriggerKeydown(event: KeyboardEvent): void {
    if (disabled) return;
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      void openList(true);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      void openList();
    }
  }

  function handleSearchKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      activeIndex = Math.max(0, firstEnabledIndex());
      void focusOption();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      void closeList(true);
    }
  }

  function handleOptionKeydown(event: KeyboardEvent, index: number): void {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      const direction = event.key === 'ArrowDown' ? 1 : -1;
      activeIndex = adjacentEnabledIndex(index, direction);
      void focusOption();
    } else if (event.key === 'Home' || event.key === 'End') {
      event.preventDefault();
      activeIndex = event.key === 'Home'
        ? Math.max(0, firstEnabledIndex())
        : [...filteredOptions].map((option) => !option.disabled).lastIndexOf(true);
      void focusOption();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      void closeList(true);
    } else if (event.key === 'Tab') {
      void closeList();
    }
  }

  $effect(() => {
    query;
    activeIndex = Math.max(0, firstEnabledIndex());
  });

  $effect(() => {
    if (disabled) open = false;
  });

  $effect(() => {
    if (!open) {
      popoverLayout = null;
      return;
    }
    const update = () => updatePopoverLayout();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  });
</script>

<div
  use:clickOutside={{ enabled: open, onoutside: () => void closeList() }}
  class:compact
  class:open
  class="multi-select-field"
  data-searchable={searchable}
>
  <span id={`${id}-label`} class="field-label">
    {label}
    {#if required}<small>Required</small>{/if}
  </span>
  <button
    bind:this={triggerElement}
    {id}
    class:placeholder={!selectedOptions.length}
    class="multi-select-trigger"
    type="button"
    {disabled}
    aria-haspopup="listbox"
    aria-expanded={open}
    aria-controls={`${id}-options`}
    aria-labelledby={`${id}-label ${id}-value`}
    onclick={() => (open ? void closeList() : void openList())}
    onkeydown={handleTriggerKeydown}
  >
    <span id={`${id}-value`}><MultiSelectSummary {values} {selectedOptions} {placeholder}/></span>
    <span class="chevron" aria-hidden="true"></span>
  </button>

  {#if open && popoverLayout}
    <MultiSelectPopover
      {id} {label} {values} {options} {filteredOptions} {canCreate} {createLabel} {query} {searchable} {required}
      layout={popoverLayout} {activeIndex} onquery={(next) => query = next} onsearchkeydown={handleSearchKeydown} {oncreate}
      ontoggle={toggle} onfocusoption={(index) => activeIndex = index}
      onoptionkeydown={handleOptionKeydown} onclear={() => onchange([])} onclose={() => void closeList(true)}
      bind:searchElement bind:listElement
    />
  {/if}
</div>

<style>
  .multi-select-field {
    position: relative;
    display: grid;
    min-width: 0;
    gap: 0.35rem;
  }

  .field-label {
    color: var(--color-ink-muted);
    font-size: 0.68rem;
    font-weight: 760;
    letter-spacing: 0.045em;
    text-transform: uppercase;
  }

  .field-label small {
    margin-left: 0.3rem;
    color: var(--color-accent-strong);
    font-size: 0.56rem;
    letter-spacing: 0.02em;
  }

  .multi-select-trigger {
    display: grid;
    width: 100%;
    min-width: 0;
    min-height: 2.55rem;
    grid-template-columns: minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 0.5rem;
    padding: 0.56rem 0.68rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    cursor: pointer;
    font: inherit;
    text-align: left;
  }

  .multi-select-trigger:hover:not(:disabled),
  .open .multi-select-trigger {
    border-color: var(--color-accent-strong);
    background: color-mix(in srgb, var(--color-accent-strong) 5%, var(--color-canvas));
  }

  .multi-select-trigger:focus-visible {
    outline: 0.16rem solid color-mix(in srgb, var(--color-accent-strong) 35%, transparent);
    outline-offset: 0.08rem;
  }

  .multi-select-trigger:disabled {
    cursor: wait;
    opacity: 0.58;
  }

  .chevron {
    width: 0.52rem;
    height: 0.52rem;
    border-right: 0.12rem solid currentColor;
    border-bottom: 0.12rem solid currentColor;
    transform: translateY(-0.13rem) rotate(45deg);
    transition: transform 130ms ease;
  }

  .open .chevron {
    transform: translateY(0.13rem) rotate(225deg);
  }

  .compact .multi-select-trigger {
    min-height: 2.3rem;
    padding-block: 0.42rem;
    font-size: 0.78rem;
  }

</style>
