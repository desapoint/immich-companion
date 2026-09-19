<script lang="ts">
  import type { SelectOption } from '../../types/ui';

  let {
    id,
    labelId,
    value,
    options,
    activeIndex,
    listStyle,
    required,
    onchoose,
    onfocusoption,
    onkeydown,
    element = $bindable<HTMLDivElement>(),
  }: {
    id: string;
    labelId: string;
    value: string;
    options: readonly SelectOption[];
    activeIndex: number;
    listStyle: string;
    required: boolean;
    onchoose: (option: SelectOption) => void;
    onfocusoption: (index: number) => void;
    onkeydown: (event: KeyboardEvent) => void;
    element?: HTMLDivElement;
  } = $props();
</script>

<div bind:this={element} {id} class="option-list" style={listStyle} role="listbox" aria-labelledby={labelId} aria-required={required}>
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
      onclick={() => onchoose(option)}
      onfocus={() => onfocusoption(index)}
      onkeydown={onkeydown}
    >
      <span>{option.label}</span>
      {#if option.value === value}<span class="check" aria-hidden="true">✓</span>{/if}
    </button>
  {/each}
</div>

<style>
  .option-list{position:fixed;z-index:1300;display:grid;width:100%;max-height:min(19rem,48vh);gap:.18rem;padding:.32rem;overflow-y:auto;border:1px solid var(--color-border-strong);border-radius:var(--radius-sm);background:var(--color-surface-raised);box-shadow:0 .8rem 2.2rem rgb(17 24 19 / 18%);overscroll-behavior:contain}
  .option{display:grid;width:100%;min-height:2.25rem;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:.75rem;padding:.48rem .58rem;border:0;border-radius:calc(var(--radius-sm) - .18rem);color:var(--color-ink-strong);background:transparent;cursor:pointer;font:inherit;text-align:left}
  .option:hover:not(:disabled),.option.active{color:var(--color-accent-strong);background:var(--color-surface-soft)}
  .option.selected{font-weight:780}.option>span:first-child{overflow-wrap:anywhere}.option:focus-visible{outline:.14rem solid var(--color-accent-strong);outline-offset:-.14rem}.option:disabled{cursor:default;opacity:.46}.check{color:var(--color-accent-strong);font-weight:900}
</style>
