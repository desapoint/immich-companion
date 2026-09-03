<script lang="ts">
  import { ArrowDown, ArrowUp } from '@lucide/svelte';
  import { tick } from 'svelte';
  import { clickOutside } from '../../lib/actions/clickOutside';

  type SortDirection = 'asc' | 'desc';
  type NormalizedSelectOption = {
    value: string;
    label: string;
    subtitle: string;
    disabled: boolean;
    direction?: SortDirection;
  };

  export type SelectOption = string | {
    value: string;
    label: string;
    subtitle?: string;
    disabled?: boolean;
    direction?: SortDirection;
  };

  let {
    id,
    label = '',
    value = $bindable<string | number>(''),
    options,
    width = 'full',
    disabled = false,
    allowEmpty = false,
    placeholder = 'Choose an option',
    searchable = false,
    searchPlaceholder = 'Search options…',
    onchange,
  }: {
    id: string;
    label?: string;
    value?: string | number;
    options: SelectOption[];
    width?: 'full' | 'content';
    disabled?: boolean;
    allowEmpty?: boolean;
    placeholder?: string;
    searchable?: boolean;
    searchPlaceholder?: string;
    onchange?: (value: string) => void;
  } = $props();

  let open = $state(false);
  let activeIndex = $state(-1);
  let searchQuery = $state('');
  let trigger = $state<HTMLButtonElement>();
  let optionsPopup = $state<HTMLDivElement>();
  let list = $state<HTMLDivElement>();
  let searchInput = $state<HTMLInputElement>();
  let widthProbe = $state<HTMLDivElement>();
  let contentTriggerWidth = $state(0);
  let intrinsicPopupWidth = $state(0);
  let popupTop = $state(0);
  let popupLeft = $state(0);
  let popupWidth = $state(0);
  let popupMaxHeight = $state(304);
  let popupPlacement = $state<'down' | 'up'>('down');
  let popupAlignment = $state<'left' | 'right' | 'viewport'>('left');

  function normalizeStringOption(option: string): NormalizedSelectOption[] {
    const directional = option.match(/^(.*)\s([↑↓])$/);
    if (!directional) return [{ value: option, label: option, subtitle: '', disabled: false }];
    const [, label, arrow] = directional;
    const currentDirection: SortDirection = arrow === '↑' ? 'asc' : 'desc';
    const alternateDirection: SortDirection = currentDirection === 'asc' ? 'desc' : 'asc';
    const valueFor = (direction: SortDirection) => `${label} ${direction === 'asc' ? '↑' : '↓'}`;
    return ([currentDirection, alternateDirection] as SortDirection[]).map((direction): NormalizedSelectOption => ({
      value: valueFor(direction),
      label,
      subtitle: '',
      disabled: false,
      direction,
    }));
  }

  function normalizeOption(option: SelectOption): NormalizedSelectOption[] {
    if (typeof option === 'string') return normalizeStringOption(option);
    return [{
      value: option.value,
      label: option.label,
      subtitle: option.subtitle ?? '',
      disabled: option.disabled ?? false,
      direction: option.direction,
    }];
  }

  const normalized: NormalizedSelectOption[] = $derived(options.flatMap(normalizeOption));
  const selected = $derived(
    normalized.find((option) => option.value === String(value))
      ?? (!allowEmpty ? normalized.find((option) => !option.disabled) : undefined),
  );
  const isEmpty = $derived(allowEmpty && String(value) === '');
  const normalizedSearch = $derived(searchQuery.trim().toLocaleLowerCase());
  const visibleOptions: NormalizedSelectOption[] = $derived(!searchable || !normalizedSearch
    ? normalized
    : normalized.filter((option) => `${option.label}\n${option.subtitle}`.toLocaleLowerCase().includes(normalizedSearch)));

  function firstEnabled(): number {
    return visibleOptions.findIndex((option) => !option.disabled);
  }

  function move(direction: 1 | -1): void {
    if (!visibleOptions.length) return;
    let index = activeIndex < 0 ? firstEnabled() : activeIndex;
    for (let attempt = 0; attempt < visibleOptions.length; attempt += 1) {
      index = (index + direction + visibleOptions.length) % visibleOptions.length;
      if (!visibleOptions[index]?.disabled) {
        activeIndex = index;
        void tick().then(() => list?.querySelector<HTMLButtonElement>(`[data-index="${index}"]`)?.focus());
        return;
      }
    }
  }

  function measureIntrinsicWidths(): void {
    if (!widthProbe) return;
    const copies = Array.from(widthProbe.querySelectorAll<HTMLElement>('[data-select-width-copy]'));
    const widestCopy = Math.max(0, ...copies.map((copy) => copy.scrollWidth));
    const placeholderWidth = widthProbe.querySelector<HTMLElement>('[data-select-width-placeholder]')?.scrollWidth ?? 0;
    const widestTriggerCopy = Math.max(widestCopy, placeholderWidth);
    const triggerChrome = 46;
    const popupChrome = 58;
    contentTriggerWidth = Math.min(320, Math.max(96, widestTriggerCopy + triggerChrome));
    intrinsicPopupWidth = Math.max(contentTriggerWidth, widestCopy + popupChrome, searchable ? 240 : 0);
  }

  function positionPopup(): void {
    if (!open || !trigger) return;
    const margin = 10;
    const gap = 5;
    const desiredMaxHeight = 304;
    const minimumUsefulHeight = 144;
    const maximumPopupWidth = Math.min(544, window.innerWidth - margin * 2);
    const rect = trigger.getBoundingClientRect();
    const spaceBelow = Math.max(0, window.innerHeight - rect.bottom - gap - margin);
    const spaceAbove = Math.max(0, rect.top - gap - margin);
    const preferDown = spaceBelow >= Math.min(desiredMaxHeight, minimumUsefulHeight) || spaceBelow >= spaceAbove;
    popupPlacement = preferDown ? 'down' : 'up';
    const available = popupPlacement === 'down' ? spaceBelow : spaceAbove;
    popupMaxHeight = Math.max(96, Math.min(desiredMaxHeight, available));

    popupWidth = Math.min(maximumPopupWidth, Math.max(rect.width, intrinsicPopupWidth));
    const leftAligned = rect.left;
    const rightAligned = rect.right - popupWidth;
    if (leftAligned + popupWidth <= window.innerWidth - margin) {
      popupLeft = Math.max(margin, leftAligned);
      popupAlignment = 'left';
    } else if (rightAligned >= margin) {
      popupLeft = rightAligned;
      popupAlignment = 'right';
    } else {
      popupLeft = Math.min(Math.max(leftAligned, margin), window.innerWidth - popupWidth - margin);
      popupAlignment = 'viewport';
    }

    popupTop = popupPlacement === 'down'
      ? rect.bottom + gap
      : Math.max(margin, rect.top - gap - Math.min(optionsPopup?.scrollHeight ?? popupMaxHeight, popupMaxHeight));
  }

  function show(): void {
    if (disabled || !normalized.length) return;
    searchQuery = '';
    activeIndex = normalized.findIndex((option) => option.value === selected?.value && !option.disabled);
    if (activeIndex < 0) activeIndex = firstEnabled();
    open = true;
    void tick().then(() => {
      measureIntrinsicWidths();
      positionPopup();
      requestAnimationFrame(positionPopup);
      if (searchable) searchInput?.focus();
      else list?.querySelector<HTMLButtonElement>(`[data-index="${activeIndex}"]`)?.focus();
    });
  }

  function choose(option: NormalizedSelectOption | undefined): void {
    if (!option || option.disabled) return;
    value = option.value;
    onchange?.(option.value);
    open = false;
    searchQuery = '';
    void tick().then(() => trigger?.focus());
  }

  function clear(): void {
    if (!allowEmpty || disabled || isEmpty) return;
    value = '';
    onchange?.('');
    open = false;
    searchQuery = '';
    void tick().then(() => trigger?.focus());
  }

  function handleTriggerKey(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      show();
    }
  }

  function handleSearchKey(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      activeIndex = firstEnabled();
      void tick().then(() => list?.querySelector<HTMLButtonElement>(`[data-index="${activeIndex}"]`)?.focus());
    } else if (event.key === 'ArrowUp') {
      event.preventDefault();
      activeIndex = visibleOptions.length;
      move(-1);
    } else if (event.key === 'Enter') {
      const first = visibleOptions[firstEnabled()];
      if (first) {
        event.preventDefault();
        choose(first);
      }
    } else if (event.key === 'Escape') {
      event.preventDefault();
      open = false;
      searchQuery = '';
      void tick().then(() => trigger?.focus());
    }
  }

  function handleOptionKey(event: KeyboardEvent, index: number): void {
    if (event.key === 'ArrowDown') { event.preventDefault(); move(1); }
    else if (event.key === 'ArrowUp') {
      event.preventDefault();
      if (searchable && index === firstEnabled()) searchInput?.focus();
      else move(-1);
    }
    else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(visibleOptions[index]); }
    else if (event.key === 'Escape') { event.preventDefault(); open = false; searchQuery = ''; void tick().then(() => trigger?.focus()); }
    else if (event.key === 'Tab') open = false;
    else if (!searchable && event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      const query = event.key.toLocaleLowerCase();
      const match = visibleOptions.findIndex((option) => !option.disabled && option.label.toLocaleLowerCase().startsWith(query));
      if (match >= 0) {
        event.preventDefault();
        activeIndex = match;
        void tick().then(() => list?.querySelector<HTMLButtonElement>(`[data-index="${match}"]`)?.focus());
      }
    }
  }

  $effect(() => {
    const optionSignature = normalized.map((option) => `${option.label}\u0000${option.subtitle}\u0000${option.direction ?? ''}`).join('\u0001');
    const currentPlaceholder = placeholder;
    const currentSearchable = searchable;
    void tick().then(() => {
      void optionSignature;
      void currentPlaceholder;
      void currentSearchable;
      measureIntrinsicWidths();
      if (open) positionPopup();
    });
  });

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

<div
  class="v2-select-field"
  data-width={width}
  style={width === 'content' && contentTriggerWidth ? `width:${contentTriggerWidth}px` : undefined}
  use:clickOutside={{ enabled: open, onoutside: () => (open = false) }}
>
  {#if label}<label class="v2-field-label" for={id}>{label}</label>{/if}
  <div class="v2-select-control">
    <button
      bind:this={trigger}
      {id}
      class="v2-select-trigger"
      data-placeholder={isEmpty || undefined}
      type="button"
      {disabled}
      aria-haspopup="listbox"
      aria-expanded={open}
      aria-controls={`${id}-options`}
      style={width === 'content' && contentTriggerWidth ? `width:${contentTriggerWidth}px` : undefined}
      onclick={() => (open ? open = false : show())}
      onkeydown={handleTriggerKey}
    >
      <span class="v2-select-trigger-copy">
        <span>{isEmpty ? placeholder : selected?.label ?? placeholder}</span>
        {#if !isEmpty && selected?.direction === 'asc'}<ArrowUp class="v2-select-direction-icon" size={14} aria-hidden="true" />{/if}
        {#if !isEmpty && selected?.direction === 'desc'}<ArrowDown class="v2-select-direction-icon" size={14} aria-hidden="true" />{/if}
      </span>
      <span class="v2-select-chevron" aria-hidden="true"></span>
    </button>
    {#if allowEmpty && !isEmpty}
      <button class="v2-select-clear" type="button" disabled={disabled} aria-label={`Clear ${label || 'selection'}`} onclick={clear}>×</button>
    {/if}
  </div>

  <div
    bind:this={widthProbe}
    aria-hidden="true"
    style="position:fixed;left:-10000px;top:-10000px;visibility:hidden;pointer-events:none;width:max-content;max-width:none;white-space:nowrap"
  >
    <span data-select-width-placeholder style="display:block;width:max-content;white-space:nowrap">{placeholder}</span>
    {#each normalized as option (`probe-${option.value}`)}
      <span data-select-width-copy style="display:flex;width:max-content;max-width:none;flex-direction:column;white-space:nowrap">
        <span style="display:flex;width:max-content;align-items:center;gap:6px;white-space:nowrap">
          <span>{option.label}</span>
          {#if option.direction === 'asc'}<ArrowUp size={14} aria-hidden="true" />{/if}
          {#if option.direction === 'desc'}<ArrowDown size={14} aria-hidden="true" />{/if}
        </span>
        {#if option.subtitle}<span style="display:block;width:max-content;white-space:nowrap">{option.subtitle}</span>{/if}
      </span>
    {/each}
  </div>

  {#if open}
    <div
      bind:this={optionsPopup}
      id={`${id}-options`}
      class="v2-select-options"
      data-searchable={searchable || undefined}
      data-placement={popupPlacement}
      data-alignment={popupAlignment}
      style={`top:${popupTop}px;left:${popupLeft}px;width:${popupWidth}px;max-height:${popupMaxHeight}px`}
    >
      {#if searchable}
        <div class="v2-select-search">
          <input
            bind:this={searchInput}
            value={searchQuery}
            placeholder={searchPlaceholder}
            aria-label={`Search ${label || 'options'}`}
            oninput={(event) => { searchQuery = event.currentTarget.value; activeIndex = -1; void tick().then(positionPopup); }}
            onkeydown={handleSearchKey}
          >
        </div>
      {/if}
      <div bind:this={list} class="v2-select-option-list" role="listbox" aria-label={label || undefined}>
        {#each visibleOptions as option, index (option.value)}
          <button
            type="button"
            role="option"
            aria-selected={!isEmpty && option.value === selected?.value}
            disabled={option.disabled}
            data-index={index}
            data-active={index === activeIndex || undefined}
            data-selected={!isEmpty && option.value === selected?.value || undefined}
            onclick={() => choose(option)}
            onfocus={() => (activeIndex = index)}
            onkeydown={(event) => handleOptionKey(event, index)}
          >
            <span class="v2-select-option-copy">
              <span class="v2-select-option-heading">
                <span class="v2-select-option-label">{option.label}</span>
                {#if option.direction === 'asc'}<ArrowUp class="v2-select-direction-icon" size={14} aria-hidden="true" />{/if}
                {#if option.direction === 'desc'}<ArrowDown class="v2-select-direction-icon" size={14} aria-hidden="true" />{/if}
              </span>
              {#if option.subtitle}<span class="v2-select-option-subtitle">{option.subtitle}</span>{/if}
            </span>
            {#if !isEmpty && option.value === selected?.value}<span class="v2-select-option-check" aria-hidden="true">✓</span>{/if}
          </button>
        {:else}
          <div class="v2-select-empty">No matching options</div>
        {/each}
      </div>
    </div>
  {/if}
</div>
