<script lang="ts">
  import {
    localChangeFillAlpha,
    localChangeFillColor,
    localChangePassesVisibilityThreshold,
  } from '../utils/localChangeVisualization';

  let {
    cells,
    style,
    labelsVisible,
    highlightColor,
    emphasis,
    minimumDifference,
  }: {
    cells: number[];
    style: string;
    labelsVisible: boolean;
    highlightColor: string;
    emphasis: number;
    minimumDifference: number;
  } = $props();
</script>

<div
  class="v2-local-change-grid"
  class:labels-visible={labelsVisible}
  {style}
  aria-hidden="true"
>
  {#each cells as changed}
    <div
      class="v2-local-change-cell"
      style:background-color={localChangeFillColor(
        highlightColor,
        localChangeFillAlpha(changed, emphasis, minimumDifference),
      )}
    >
      <span
        class="v2-local-change-label"
        class:difference-visible={localChangePassesVisibilityThreshold(changed, minimumDifference)}
      >
        {Math.round(changed)}%
      </span>
    </div>
  {/each}
</div>

<style>
  .v2-local-change-grid {
    position:absolute;
    z-index:2;
    display:grid;
    pointer-events:none;
    contain:layout paint style;
  }
  .v2-local-change-cell {
    position:relative;
    min-width:0;
    min-height:0;
    overflow:hidden;
    box-shadow:inset 0 0 0 .5px rgba(255,255,255,.24);
  }
  .v2-local-change-label {
    position:absolute;
    left:50%;
    top:50%;
    transform:translate(-50%, -50%);
    visibility:hidden;
    color:#fff;
    font:700 12px/1.2 system-ui, sans-serif;
    white-space:nowrap;
    text-shadow:
      -1px -1px 0 rgba(0,0,0,.9),
      1px -1px 0 rgba(0,0,0,.9),
      -1px 1px 0 rgba(0,0,0,.9),
      1px 1px 0 rgba(0,0,0,.9),
      0 1px 2px rgba(0,0,0,.95);
    pointer-events:none;
  }
  .v2-local-change-grid.labels-visible .v2-local-change-label.difference-visible {
    visibility:visible;
  }
</style>
