<script lang="ts">
  import { tick } from 'svelte';

  import { clickOutside } from '../../actions/clickOutside';
  import type { SelectOption } from '../../types/ui';
  import {
    floatingPopoverLayout,
    type FloatingPopoverLayout,
  } from '../../utils/floatingPopover';

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
  const summary = $derived.by(() => {
    if (!selectedOptions.length) return placeholder;
    if (selectedOptions.length <= 2) return selectedOptions.map((option) => option.label).join(', ');
    return `${selectedOptions.length} selected`;
  });
  const filteredOptions = $derived.by(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!searchable || !normalized) return options;
    return options.filter((option) => option.label.toLocaleLowerCase().includes(normalized));
  });
  const canCreate = $derived.by(() => {
    const value = query.trim();
    return allowCreate && Boolean(value) && !options.some(
      (option) => option.label.trim().toLocaleLowerCase() === value.toLocaleLowerCase(),
    );
  });

  function firstEnabledIndex(): number {
    return filteredOptions.findIndex((option) => !option.disabled);
  }

  function adjacentEnabledIndex(start: number, direction: 1 | -1): number {
    if (!filteredOptions.length) return -1;
    let index = start;
    for (let attempt = 0; attempt < filteredOptions.length; attempt += 1) {
      index = (index + direction + filteredOptions.length) % filteredOptions.length;
      if (!filteredOptions[index]?.disabled) return index;
    }
    return -1;
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
    <span id={`${id}-value`} class="selected-value">{summary}</span>
    <span class="selection-count" aria-hidden="true">{values.length || ''}</span>
    <span class="chevron" aria-hidden="true"></span>
  </button>

  {#if open && popoverLayout}
    <div
      class:above={popoverLayout.placement === 'above'}
      class="multi-select-popover"
      style:left={`${popoverLayout.left}px`}
      style:top={popoverLayout.top === null ? 'auto' : `${popoverLayout.top}px`}
      style:bottom={popoverLayout.bottom === null ? 'auto' : `${popoverLayout.bottom}px`}
      style:width={`${popoverLayout.width}px`}
      style:max-height={`${popoverLayout.maxHeight}px`}
    >
      {#if searchable}
        <label class="option-search">
          <span>Search {label.toLocaleLowerCase()}</span>
          <input
            bind:this={searchElement}
            type="search"
            bind:value={query}
            placeholder={`Search ${label.toLocaleLowerCase()}`}
            autocomplete="off"
            onkeydown={handleSearchKeydown}
          />
        </label>
      {/if}

      <div
        bind:this={listElement}
        id={`${id}-options`}
        class="option-list"
        role="listbox"
        aria-labelledby={`${id}-label`}
        aria-multiselectable="true"
        aria-required={required}
      >
        {#if canCreate}
          <button
            class="option create-option"
            type="button"
            role="option"
            aria-selected="false"
            onclick={() => oncreate?.(query.trim())}
          >
            <span>{createLabel} “{query.trim()}”</span>
            <span aria-hidden="true">＋</span>
          </button>
        {/if}
        {#each filteredOptions as option, index (option.value)}
          <button
            class:active={index === activeIndex}
            class:selected={values.includes(option.value)}
            class="option"
            type="button"
            role="option"
            aria-selected={values.includes(option.value)}
            disabled={option.disabled}
            tabindex={index === activeIndex ? 0 : -1}
            data-option-index={index}
            onclick={() => toggle(option)}
            onfocus={() => (activeIndex = index)}
            onkeydown={(event) => handleOptionKeydown(event, index)}
          >
            <span>{option.label}</span>
            <span class="check" aria-hidden="true">{values.includes(option.value) ? '✓' : ''}</span>
          </button>
        {:else}
          <p>{options.length ? 'No matching values.' : 'No values available.'}</p>
        {/each}
      </div>

      <footer>
        <button type="button" disabled={!values.length} onclick={() => onchange([])}>Clear</button>
        <button class="done" type="button" onclick={() => void closeList(true)}>Done</button>
      </footer>
    </div>
  {/if}
</div>

<style>
  .multi-select-field {
    position: relative;
    display: grid;
    min-width: 0;
    gap: 0.35rem;
  }

  .field-label,
  .option-search > span {
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

  .multi-select-trigger:focus-visible,
  .option-search input:focus-visible {
    outline: 0.16rem solid color-mix(in srgb, var(--color-accent-strong) 35%, transparent);
    outline-offset: 0.08rem;
  }

  .multi-select-trigger:disabled {
    cursor: wait;
    opacity: 0.58;
  }

  .selected-value {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .placeholder .selected-value {
    color: var(--color-ink-muted);
  }

  .selection-count {
    display: grid;
    min-width: 1.25rem;
    min-height: 1.25rem;
    padding-inline: 0.25rem;
    place-items: center;
    border-radius: 999px;
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
    font-size: 0.64rem;
    font-weight: 800;
  }

  .selection-count:empty {
    visibility: hidden;
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

  .multi-select-popover {
    position: fixed;
    z-index: 1000;
    display: flex;
    flex-direction: column;
    min-height: 0;
    gap: 0.4rem;
    padding: 0.42rem;
    overflow: hidden;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    background: var(--color-surface-raised);
    box-shadow: 0 0.8rem 2.2rem rgb(17 24 19 / 18%);
  }

  .option-search {
    display: grid;
    gap: 0.3rem;
  }

  .option-search input {
    width: 100%;
    min-height: 2.3rem;
    padding: 0.45rem 0.55rem;
    border: 1px solid var(--color-border-strong);
    border-radius: calc(var(--radius-sm) - 0.12rem);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    font: inherit;
    font-size: 0.76rem;
  }

  .option-list {
    display: grid;
    flex: 1 1 auto;
    min-height: 0;
    max-height: none;
    gap: 0.18rem;
    overflow-y: auto;
    overscroll-behavior: contain;
  }

  .option {
    display: grid;
    width: 100%;
    min-height: 2.25rem;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.75rem;
    padding: 0.48rem 0.58rem;
    border: 0;
    border-radius: calc(var(--radius-sm) - 0.18rem);
    color: var(--color-ink-strong);
    background: transparent;
    cursor: pointer;
    font: inherit;
    text-align: left;
  }

  .option:hover:not(:disabled),
  .option.active {
    color: var(--color-accent-strong);
    background: var(--color-surface-soft);
  }

  .create-option {
    color: var(--color-accent-strong);
    background: color-mix(in srgb, var(--color-accent-strong) 7%, transparent);
    font-weight: 760;
  }

  .option.selected {
    color: var(--color-accent-strong);
    background: color-mix(in srgb, var(--color-accent-strong) 8%, transparent);
    box-shadow: inset 0 0 0 0.1rem color-mix(in srgb, var(--color-accent-strong) 46%, transparent);
  }

  .option > span:first-child {
    overflow-wrap: anywhere;
  }

  .option:focus-visible {
    outline: 0.14rem solid var(--color-accent-strong);
    outline-offset: -0.14rem;
  }

  .option:disabled,
  footer button:disabled {
    cursor: default;
    opacity: 0.46;
  }

  .check {
    min-width: 1rem;
    color: var(--color-accent-strong);
    font-weight: 900;
  }

  .option-list p {
    margin: 0;
    padding: 0.7rem;
    color: var(--color-ink-muted);
    font-size: 0.72rem;
  }

  footer {
    display: flex;
    justify-content: flex-end;
    gap: 0.4rem;
    padding-top: 0.38rem;
    border-top: 1px solid var(--color-border-subtle);
  }

  footer button {
    min-height: 2.1rem;
    padding: 0.38rem 0.62rem;
    border: 1px solid var(--color-border-strong);
    border-radius: calc(var(--radius-sm) - 0.12rem);
    color: var(--color-ink-muted);
    background: var(--color-surface-soft);
    cursor: pointer;
    font: inherit;
    font-size: 0.7rem;
    font-weight: 760;
  }

  footer .done {
    border-color: var(--color-accent-strong);
    color: var(--color-ink-inverse);
    background: var(--color-accent-strong);
  }

  .compact .multi-select-trigger {
    min-height: 2.3rem;
    padding-block: 0.42rem;
    font-size: 0.78rem;
  }

  .compact .option {
    min-height: 2.1rem;
    font-size: 0.78rem;
  }
</style>
