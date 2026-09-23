<script lang="ts">
  import type { ComparisonMode } from '../types/comparisonMode';

  const visualModes: ComparisonMode[] = ['Side by side', 'Swipe', 'Flicker'];
  const analysisModes: ComparisonMode[] = ['Transparency', 'Difference', 'Local changes'];
  const modes: ComparisonMode[] = [...visualModes, ...analysisModes];

  let {
    mode = $bindable<ComparisonMode>('Side by side'),
  }: {
    mode?: ComparisonMode;
  } = $props();

  function selectMode(value: string): void {
    if (modes.includes(value as ComparisonMode)) mode = value as ComparisonMode;
  }
</script>

<div class="comparison-mode-selector" data-testid="comparison-mode-selector">
  <div class="comparison-mode-desktop" role="group" aria-label="Comparison mode">
    <fieldset>
      <legend>Visual modes</legend>
      <div class="comparison-mode-options">
        {#each visualModes as option (option)}
          <button type="button" aria-pressed={mode === option} onclick={() => selectMode(option)}>{option}</button>
        {/each}
      </div>
    </fieldset>
    <fieldset>
      <legend>Analysis modes</legend>
      <div class="comparison-mode-options">
        {#each analysisModes as option (option)}
          <button type="button" aria-pressed={mode === option} onclick={() => selectMode(option)}>{option}</button>
        {/each}
      </div>
    </fieldset>
  </div>

  <label class="comparison-mode-mobile">
    <span>Comparison mode</span>
    <select aria-label="Comparison mode" value={mode} onchange={(event) => selectMode((event.currentTarget as HTMLSelectElement).value)}>
      <optgroup label="Visual modes">
        {#each visualModes as option (option)}<option value={option}>{option}</option>{/each}
      </optgroup>
      <optgroup label="Analysis modes">
        {#each analysisModes as option (option)}<option value={option}>{option}</option>{/each}
      </optgroup>
    </select>
  </label>
</div>

<style>
  .comparison-mode-selector { min-width: 0; }
  .comparison-mode-desktop { display: flex; flex-wrap: wrap; gap: 8px; }
  fieldset { display: flex; align-items: center; gap: 6px; min-width: 0; margin: 0; padding: 0; border: 0; }
  legend { flex: 0 0 auto; padding: 0; color: var(--v2-muted); font-size: 10px; font-weight: 750; letter-spacing: .04em; text-transform: uppercase; }
  .comparison-mode-options { display: flex; min-width: 0; overflow: hidden; border: 1px solid var(--v2-line); border-radius: 8px; }
  button { border: 0; border-right: 1px solid var(--v2-line); background: var(--v2-surface); color: var(--v2-muted); padding: 6px 9px; font: inherit; font-size: 11px; font-weight: 700; white-space: nowrap; cursor: pointer; }
  button:last-child { border-right: 0; }
  button:hover { color: var(--v2-text); background: var(--v2-surface-2); }
  button[aria-pressed="true"] { background: var(--v2-accent-2); color: var(--v2-text); }
  button:focus-visible, select:focus-visible { outline: 2px solid var(--v2-accent); outline-offset: 1px; }
  .comparison-mode-mobile { display: none; }

  @media (max-width: 620px) {
    .comparison-mode-desktop { display: none; }
    .comparison-mode-mobile { display: grid; gap: 4px; color: var(--v2-muted); font-size: 10px; font-weight: 750; letter-spacing: .04em; text-transform: uppercase; }
    select { width: 100%; min-height: 36px; border: 1px solid var(--v2-line); border-radius: 8px; background: var(--v2-surface); color: var(--v2-text); padding: 7px 9px; font: inherit; font-size: 13px; letter-spacing: normal; text-transform: none; }
  }
</style>
