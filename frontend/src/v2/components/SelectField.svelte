<script lang="ts">
  import { tick } from 'svelte';
  import { clickOutside } from '../../lib/actions/clickOutside';

  export type SelectOption = string | { value: string; label: string; disabled?: boolean };

  let {
    id,
    label = '',
    value = $bindable<string | number>(''),
    options,
    width = 'full',
    disabled = false,
    placeholder = 'Choose an option',
    onchange,
  }: {
    id: string;
    label?: string;
    value?: string | number;
    options: SelectOption[];
    width?: 'full' | 'content';
    disabled?: boolean;
    placeholder?: string;
    onchange?: (value: string) => void;
  } = $props();

  let open = $state(false);
  let activeIndex = $state(-1);
  let trigger = $state<HTMLButtonElement>();
  let list = $state<HTMLDivElement>();

  const normalized = $derived(options.map((option) => typeof option === 'string'
    ? { value: option, label: option, disabled: false }
    : { disabled: false, ...option }));
  const selected = $derived(normalized.find((option) => option.value === String(value)) ?? normalized[0]);

  function firstEnabled(): number {
    return normalized.findIndex((option) => !option.disabled);
  }

  function move(direction: 1 | -1): void {
    if (!normalized.length) return;
    let index = activeIndex < 0 ? firstEnabled() : activeIndex;
    for (let attempt = 0; attempt < normalized.length; attempt += 1) {
      index = (index + direction + normalized.length) % normalized.length;
      if (!normalized[index]?.disabled) {
        activeIndex = index;
        void tick().then(() => list?.querySelector<HTMLButtonElement>(`[data-index="${index}"]`)?.focus());
        return;
      }
    }
  }

  function show(): void {
    if (disabled || !normalized.length) return;
    activeIndex = normalized.findIndex((option) => option.value === String(value) && !option.disabled);
    if (activeIndex < 0) activeIndex = firstEnabled();
    open = true;
    void tick().then(() => list?.querySelector<HTMLButtonElement>(`[data-index="${activeIndex}"]`)?.focus());
  }

  function choose(index: number): void {
    const option = normalized[index];
    if (!option || option.disabled) return;
    value = option.value;
    onchange?.(option.value);
    open = false;
    void tick().then(() => trigger?.focus());
  }

  function handleTriggerKey(event: KeyboardEvent): void {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp' || event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      show();
    }
  }

  function handleOptionKey(event: KeyboardEvent, index: number): void {
    if (event.key === 'ArrowDown') { event.preventDefault(); move(1); }
    else if (event.key === 'ArrowUp') { event.preventDefault(); move(-1); }
    else if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); choose(index); }
    else if (event.key === 'Escape') { event.preventDefault(); open = false; void tick().then(() => trigger?.focus()); }
    else if (event.key === 'Tab') open = false;
    else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      const query = event.key.toLocaleLowerCase();
      const match = normalized.findIndex((option) => !option.disabled && option.label.toLocaleLowerCase().startsWith(query));
      if (match >= 0) {
        event.preventDefault();
        activeIndex = match;
        void tick().then(() => list?.querySelector<HTMLButtonElement>(`[data-index="${match}"]`)?.focus());
      }
    }
  }
</script>

<div class="v2-select-field" data-width={width} use:clickOutside={{ enabled: open, onoutside: () => (open = false) }}>
  {#if label}<label class="v2-field-label" for={id}>{label}</label>{/if}
  <button
    bind:this={trigger}
    {id}
    class="v2-select-trigger"
    type="button"
    {disabled}
    aria-haspopup="listbox"
    aria-expanded={open}
    aria-controls={`${id}-options`}
    onclick={() => (open ? open = false : show())}
    onkeydown={handleTriggerKey}
  >
    <span>{selected?.label ?? placeholder}</span>
    <span class="v2-select-chevron" aria-hidden="true"></span>
  </button>

  {#if open}
    <div bind:this={list} id={`${id}-options`} class="v2-select-options" role="listbox" aria-label={label || undefined}>
      {#each normalized as option, index (option.value)}
        <button
          type="button"
          role="option"
          aria-selected={option.value === String(value)}
          disabled={option.disabled}
          data-index={index}
          data-active={index === activeIndex || undefined}
          data-selected={option.value === String(value) || undefined}
          onclick={() => choose(index)}
          onfocus={() => (activeIndex = index)}
          onkeydown={(event) => handleOptionKey(event, index)}
        >
          <span>{option.label}</span>
          {#if option.value === String(value)}<span aria-hidden="true">✓</span>{/if}
        </button>
      {/each}
    </div>
  {/if}
</div>
