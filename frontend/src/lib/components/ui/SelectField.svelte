<script lang="ts">
  import { onDestroy, tick } from 'svelte';

  import { clickOutside } from '../../actions/clickOutside';

  export interface SelectOption {
    value: string;
    label: string;
    disabled?: boolean;
  }

  interface Props {
    id: string;
    label: string;
    value: string;
    options: SelectOption[];
    disabled?: boolean;
    required?: boolean;
    compact?: boolean;
    onchange: (value: string) => void;
  }

  let {
    id,
    label,
    value,
    options,
    disabled = false,
    required = false,
    compact = false,
    onchange,
  }: Props = $props();

  let triggerElement = $state<HTMLButtonElement>();
  let listElement = $state<HTMLDivElement>();
  let open = $state(false);
  let activeIndex = $state(-1);
  let typeahead = '';
  let typeaheadTimer: ReturnType<typeof setTimeout> | undefined;

  const selectedOption = $derived(options.find((option) => option.value === value));

  function firstEnabledIndex(): number {
    return options.findIndex((option) => !option.disabled);
  }

  function lastEnabledIndex(): number {
    for (let index = options.length - 1; index >= 0; index -= 1) {
      if (!options[index]?.disabled) return index;
    }
    return -1;
  }

  function selectedIndex(): number {
    const index = options.findIndex((option) => option.value === value && !option.disabled);
    return index >= 0 ? index : firstEnabledIndex();
  }

  function adjacentEnabledIndex(start: number, direction: 1 | -1): number {
    if (options.length === 0) return -1;
    let index = start;
    for (let attempt = 0; attempt < options.length; attempt += 1) {
      index = (index + direction + options.length) % options.length;
      if (!options[index]?.disabled) return index;
    }
    return -1;
  }

  async function focusActiveOption(): Promise<void> {
    await tick();
    listElement?.querySelector<HTMLButtonElement>(`[data-option-index="${activeIndex}"]`)?.focus();
  }

  async function openList(preferredIndex = selectedIndex()): Promise<void> {
    if (disabled || options.length === 0) return;
    activeIndex = preferredIndex >= 0 ? preferredIndex : firstEnabledIndex();
    open = true;
    await focusActiveOption();
  }

  async function closeList(restoreFocus = false): Promise<void> {
    open = false;
    if (restoreFocus) {
      await tick();
      triggerElement?.focus();
    }
  }

  async function moveActive(direction: 1 | -1): Promise<void> {
    activeIndex = adjacentEnabledIndex(activeIndex, direction);
    await focusActiveOption();
  }

  function choose(option: SelectOption): void {
    if (disabled || option.disabled) return;
    onchange(option.value);
    void closeList(true);
  }

  function handleTriggerKeydown(event: KeyboardEvent): void {
    if (disabled) return;
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      void openList(selectedIndex());
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      void openList(lastEnabledIndex());
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      void openList();
    } else if (event.key === 'Home') {
      event.preventDefault();
      void openList(firstEnabledIndex());
    } else if (event.key === 'End') {
      event.preventDefault();
      void openList(lastEnabledIndex());
    }
  }

  function handleTypeahead(key: string): void {
    typeahead += key.toLocaleLowerCase();
    if (typeaheadTimer) clearTimeout(typeaheadTimer);
    typeaheadTimer = setTimeout(() => (typeahead = ''), 600);
    const match = options.findIndex((option) => (
      !option.disabled && option.label.toLocaleLowerCase().startsWith(typeahead)
    ));
    if (match >= 0) {
      activeIndex = match;
      void focusActiveOption();
    }
  }

  function handleOptionKeydown(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      event.stopPropagation();
      void moveActive(1);
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      event.stopPropagation();
      void moveActive(-1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      event.stopPropagation();
      activeIndex = firstEnabledIndex();
      void focusActiveOption();
    } else if (event.key === 'End') {
      event.preventDefault();
      event.stopPropagation();
      activeIndex = lastEnabledIndex();
      void focusActiveOption();
    } else if (event.key === 'Escape') {
      event.preventDefault();
      event.stopPropagation();
      void closeList(true);
    } else if (event.key === 'Tab') {
      void closeList();
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      event.preventDefault();
      handleTypeahead(event.key);
    }
  }

  $effect(() => {
    if (disabled) open = false;
  });

  onDestroy(() => {
    if (typeaheadTimer) clearTimeout(typeaheadTimer);
  });
</script>

<div
  use:clickOutside={{ enabled: open, onoutside: () => void closeList() }}
  class:compact
  class:open
  class="select-field"
>
  <span id={`${id}-label`} class="field-label">
    {label}
    {#if required}<small>Required</small>{/if}
  </span>
  <button
    bind:this={triggerElement}
    {id}
    class="select-trigger"
    class:placeholder={!selectedOption}
    type="button"
    {disabled}
    aria-haspopup="listbox"
    aria-expanded={open}
    aria-controls={`${id}-options`}
    aria-labelledby={`${id}-label ${id}-value`}
    onclick={() => (open ? void closeList() : void openList())}
    onkeydown={handleTriggerKeydown}
  >
    <span id={`${id}-value`} class="selected-value">{selectedOption?.label ?? 'Choose an option'}</span>
    <span class="chevron" aria-hidden="true"></span>
  </button>

  {#if open}
    <div
      bind:this={listElement}
      id={`${id}-options`}
      class="option-list"
      role="listbox"
      aria-labelledby={`${id}-label`}
      aria-required={required}
    >
      {#each options as option, index (option.value)}
        <button
          id={`${id}-option-${index}`}
          class:active={index === activeIndex}
          class:selected={option.value === value}
          class="option"
          type="button"
          role="option"
          aria-selected={option.value === value}
          disabled={option.disabled}
          tabindex={index === activeIndex ? 0 : -1}
          data-option-index={index}
          onclick={() => choose(option)}
          onfocus={() => (activeIndex = index)}
          onkeydown={handleOptionKeydown}
        >
          <span>{option.label}</span>
          {#if option.value === value}
            <span class="check" aria-hidden="true">✓</span>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .select-field {
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

  .select-trigger {
    display: grid;
    width: 100%;
    min-width: 0;
    min-height: 2.55rem;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.65rem;
    padding: 0.56rem 0.68rem;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    color: var(--color-ink-strong);
    background: var(--color-canvas);
    cursor: pointer;
    font: inherit;
    text-align: left;
  }

  .select-trigger:hover:not(:disabled),
  .open .select-trigger {
    border-color: var(--color-accent-strong);
    background: color-mix(in srgb, var(--color-accent-strong) 5%, var(--color-canvas));
  }

  .select-trigger:focus-visible {
    outline: 0.16rem solid color-mix(in srgb, var(--color-accent-strong) 35%, transparent);
    outline-offset: 0.08rem;
  }

  .select-trigger:disabled {
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

  .option-list {
    position: absolute;
    z-index: 80;
    top: calc(100% + 0.35rem);
    left: 0;
    display: grid;
    width: 100%;
    max-height: min(19rem, 48vh);
    gap: 0.18rem;
    padding: 0.32rem;
    overflow-y: auto;
    border: 1px solid var(--color-border-strong);
    border-radius: var(--radius-sm);
    background: var(--color-surface-raised);
    box-shadow: 0 0.8rem 2.2rem rgb(17 24 19 / 18%);
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

  .option.selected {
    font-weight: 780;
  }

  .option > span:first-child {
    overflow-wrap: anywhere;
  }

  .option:focus-visible {
    outline: 0.14rem solid var(--color-accent-strong);
    outline-offset: -0.14rem;
  }

  .option:disabled {
    cursor: default;
    opacity: 0.46;
  }

  .check {
    color: var(--color-accent-strong);
    font-weight: 900;
  }

  .compact .select-trigger {
    min-height: 2.3rem;
    padding-block: 0.42rem;
    font-size: 0.78rem;
  }

  .compact .option {
    min-height: 2.1rem;
    font-size: 0.78rem;
  }
</style>
