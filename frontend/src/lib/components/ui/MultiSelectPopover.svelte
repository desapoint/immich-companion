<script lang="ts">
  import type { SelectOption } from '../../types/ui';
  import type { FloatingPopoverLayout } from '../../utils/floatingPopover';

  let {
    id, label, values, options, filteredOptions, canCreate, createLabel, query, searchable, required, layout, activeIndex,
    onquery, onsearchkeydown, oncreate, ontoggle, onfocusoption, onoptionkeydown, onclear, onclose,
    searchElement = $bindable<HTMLInputElement>(), listElement = $bindable<HTMLDivElement>(),
  }: {
    id: string; label: string; values: readonly string[]; options: readonly SelectOption[]; filteredOptions: readonly SelectOption[];
    canCreate: boolean; createLabel: string; query: string; searchable: boolean; required: boolean; layout: FloatingPopoverLayout;
    activeIndex: number; onquery: (value: string) => void; onsearchkeydown: (event: KeyboardEvent) => void; oncreate?: (value: string) => void;
    ontoggle: (option: SelectOption) => void; onfocusoption: (index: number) => void;
    onoptionkeydown: (event: KeyboardEvent, index: number) => void; onclear: () => void; onclose: () => void;
    searchElement?: HTMLInputElement; listElement?: HTMLDivElement;
  } = $props();
</script>

<div class:above={layout.placement === 'above'} class="multi-select-popover" style:left={`${layout.left}px`} style:top={layout.top === null ? 'auto' : `${layout.top}px`} style:bottom={layout.bottom === null ? 'auto' : `${layout.bottom}px`} style:width={`${layout.width}px`} style:max-height={`${layout.maxHeight}px`}>
  {#if searchable}<label class="option-search"><span>Search {label.toLocaleLowerCase()}</span><input bind:this={searchElement} type="search" value={query} placeholder={`Search ${label.toLocaleLowerCase()}`} autocomplete="off" oninput={(event) => onquery(event.currentTarget.value)} onkeydown={onsearchkeydown} /></label>{/if}
  <div bind:this={listElement} id={`${id}-options`} class="option-list" role="listbox" aria-labelledby={`${id}-label`} aria-multiselectable="true" aria-required={required}>
    {#if canCreate}<button class="option create-option" type="button" role="option" aria-selected="false" onclick={() => oncreate?.(query.trim())}><span>{createLabel} “{query.trim()}”</span><span aria-hidden="true">＋</span></button>{/if}
    {#each filteredOptions as option, index (option.value)}
      <button class:active={index === activeIndex} class:selected={values.includes(option.value)} class="option" type="button" role="option" aria-selected={values.includes(option.value)} disabled={option.disabled} tabindex={index === activeIndex ? 0 : -1} data-option-index={index} onclick={() => ontoggle(option)} onfocus={() => onfocusoption(index)} onkeydown={(event) => onoptionkeydown(event, index)}><span>{option.label}</span><span class="check" aria-hidden="true">{values.includes(option.value) ? '✓' : ''}</span></button>
    {:else}<p>{options.length ? 'No matching values.' : 'No values available.'}</p>{/each}
  </div>
  <footer><button type="button" disabled={!values.length} onclick={onclear}>Clear</button><button class="done" type="button" onclick={onclose}>Done</button></footer>
</div>

<style>
  .multi-select-popover{position:fixed;z-index:1000;display:flex;flex-direction:column;min-height:0;gap:.4rem;padding:.42rem;overflow:hidden;border:1px solid var(--color-border-strong);border-radius:var(--radius-sm);background:var(--color-surface-raised);box-shadow:0 .8rem 2.2rem rgb(17 24 19 / 18%)}
  .option-search{display:grid;gap:.3rem}.option-search>span{color:var(--color-ink-muted);font-size:.68rem;font-weight:760;letter-spacing:.045em;text-transform:uppercase}.option-search input{width:100%;min-height:2.3rem;padding:.45rem .55rem;border:1px solid var(--color-border-strong);border-radius:calc(var(--radius-sm) - .12rem);color:var(--color-ink-strong);background:var(--color-canvas);font:inherit;font-size:.76rem}
  .option-list{display:grid;flex:1 1 auto;min-height:0;max-height:none;gap:.18rem;overflow-y:auto;overscroll-behavior:contain}.option{display:grid;width:100%;min-height:2.25rem;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:.75rem;padding:.48rem .58rem;border:0;border-radius:calc(var(--radius-sm) - .18rem);color:var(--color-ink-strong);background:transparent;cursor:pointer;font:inherit;text-align:left}.option:hover:not(:disabled),.option.active{color:var(--color-accent-strong);background:var(--color-surface-soft)}.create-option{color:var(--color-accent-strong);background:color-mix(in srgb,var(--color-accent-strong) 7%,transparent);font-weight:760}.option.selected{color:var(--color-accent-strong);background:color-mix(in srgb,var(--color-accent-strong) 8%,transparent);box-shadow:inset 0 0 0 .1rem color-mix(in srgb,var(--color-accent-strong) 46%,transparent)}.option>span:first-child{overflow-wrap:anywhere}.option:focus-visible{outline:.14rem solid var(--color-accent-strong);outline-offset:-.14rem}.option:disabled,footer button:disabled{cursor:default;opacity:.46}.check{min-width:1rem;color:var(--color-accent-strong);font-weight:900}.option-list p{margin:0;padding:.7rem;color:var(--color-ink-muted);font-size:.72rem}
  footer{display:flex;justify-content:flex-end;gap:.4rem;padding-top:.38rem;border-top:1px solid var(--color-border-subtle)}footer button{min-height:2.1rem;padding:.38rem .62rem;border:1px solid var(--color-border-strong);border-radius:calc(var(--radius-sm) - .12rem);color:var(--color-ink-muted);background:var(--color-surface-soft);cursor:pointer;font:inherit;font-size:.7rem;font-weight:760}footer .done{border-color:var(--color-accent-strong);color:var(--color-ink-inverse);background:var(--color-accent-strong)}
</style>
