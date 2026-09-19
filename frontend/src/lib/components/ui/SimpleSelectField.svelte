<script lang="ts">
import { onDestroy, onMount, tick } from 'svelte';

  import { clickOutside } from '../../actions/clickOutside';
  import type { SelectOption } from '../../types/ui';
  import SelectOptionList from './SelectOptionList.svelte';
  import { adjacentEnabledIndex, firstEnabledIndex, lastEnabledIndex, selectedOptionIndex, typeaheadIndex } from './selectOptions';

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
  let listStyle = $state('');

  const selectedOption = $derived(options.find((option) => option.value === value));

  function selectedIndex(): number {
    return selectedOptionIndex(options, value);
  }

  async function focusActiveOption(): Promise<void> {
    await tick();
    listElement?.querySelector<HTMLButtonElement>(`[data-option-index="${activeIndex}"]`)?.focus();
  }

  async function openList(preferredIndex = selectedIndex()): Promise<void> {
    if (disabled || options.length === 0) return;
    activeIndex = preferredIndex >= 0 ? preferredIndex : firstEnabledIndex(options);
    open = true;
    await tick();
    positionList();
    await focusActiveOption();
  }

  async function closeList(restoreFocus = false): Promise<void> {
    open = false;
    if (restoreFocus) {
      await tick();
      triggerElement?.focus();
    }
  }

  function positionList(): void {
    if (!triggerElement) return;
    const rect = triggerElement.getBoundingClientRect();
    const height = listElement?.offsetHeight ?? Math.min(304, window.innerHeight * 0.48);
    const top = rect.bottom + 6 + height <= window.innerHeight - 10 || rect.top < height + 16
      ? Math.min(rect.bottom + 6, window.innerHeight - height - 10)
      : rect.top - height - 6;
    listStyle = `top:${Math.max(10, top)}px;left:${rect.left}px;width:${rect.width}px;`;
  }

  async function moveActive(direction: 1 | -1): Promise<void> {
    activeIndex = adjacentEnabledIndex(options, activeIndex, direction);
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
      void openList(lastEnabledIndex(options));
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      void openList();
    } else if (event.key === 'Home') {
      event.preventDefault();
      void openList(firstEnabledIndex(options));
    } else if (event.key === 'End') {
      event.preventDefault();
      void openList(lastEnabledIndex(options));
    }
  }

  function handleTypeahead(key: string): void {
    typeahead += key.toLocaleLowerCase();
    if (typeaheadTimer) clearTimeout(typeaheadTimer);
    typeaheadTimer = setTimeout(() => (typeahead = ''), 600);
    const match = typeaheadIndex(options, typeahead);
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
      activeIndex = firstEnabledIndex(options);
      void focusActiveOption();
    } else if (event.key === 'End') {
      event.preventDefault();
      event.stopPropagation();
      activeIndex = lastEnabledIndex(options);
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

  onMount(() => {
    const reposition = () => open && positionList();
    window.addEventListener('resize', reposition);
    window.addEventListener('scroll', reposition, true);
    return () => {
      window.removeEventListener('resize', reposition);
      window.removeEventListener('scroll', reposition, true);
    };
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
    <SelectOptionList
      id={`${id}-options`}
      labelId={`${id}-label`}
      {value}
      {options}
      {activeIndex}
      {listStyle}
      {required}
      onchoose={choose}
      onfocusoption={(index) => (activeIndex = index)}
      onkeydown={handleOptionKeydown}
      bind:element={listElement}
    />
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

  .compact .select-trigger {
    min-height: 2.3rem;
    padding-block: 0.42rem;
    font-size: 0.78rem;
  }

</style>
