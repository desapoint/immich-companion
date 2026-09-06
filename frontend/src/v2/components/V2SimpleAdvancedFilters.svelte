<script lang="ts">
  import V2Checkbox from './V2Checkbox.svelte';
  import V2Field from './V2Field.svelte';

  type SimpleAdvancedFilters = {
    albumIds: string;
    tagIds: string;
    noAlbum: boolean;
    noTag: boolean;
    takenAfter: string;
    takenBefore: string;
    minWidth: string;
    maxWidth: string;
    minHeight: string;
    maxHeight: string;
    minAspectRatio: string;
    maxAspectRatio: string;
  };

  let {
    filters,
    onchange,
  }: {
    filters: SimpleAdvancedFilters;
    onchange: (filters: SimpleAdvancedFilters) => void;
  } = $props();

  const relationCount = (value: string) => value.split(',').map((part) => part.trim()).filter(Boolean).length;
  const activeCount = $derived(
    relationCount(filters.albumIds)
    + relationCount(filters.tagIds)
    + Number(filters.noAlbum)
    + Number(filters.noTag)
    + [
      filters.takenAfter,
      filters.takenBefore,
      filters.minWidth,
      filters.maxWidth,
      filters.minHeight,
      filters.maxHeight,
      filters.minAspectRatio,
      filters.maxAspectRatio,
    ].filter((value) => value.trim()).length,
  );

  function update<K extends keyof SimpleAdvancedFilters>(key: K, value: SimpleAdvancedFilters[K]) {
    onchange({ ...filters, [key]: value });
  }
</script>

<details class="v2-simple-advanced">
  <summary>
    <span class="v2-simple-advanced-title">Advanced</span>
    <span class="v2-simple-advanced-summary">
      {activeCount > 0 ? `${activeCount} active filter${activeCount === 1 ? '' : 's'}` : 'Albums, tags, dates, dimensions and aspect ratio'}
    </span>
    <span class="v2-simple-advanced-marker" aria-hidden="true">+</span>
  </summary>

  <div class="v2-simple-advanced-fields">
    <div class="v2-simple-advanced-relation">
      <V2Field
        label="Albums"
        value={filters.albumIds}
        placeholder="Album names or IDs, comma-separated"
        disabled={filters.noAlbum}
        onchange={(value) => update('albumIds', value)}
      />
      <V2Checkbox
        label="No album"
        checked={filters.noAlbum}
        onchange={(checked) => onchange({ ...filters, noAlbum: checked, albumIds: checked ? '' : filters.albumIds })}
      />
    </div>

    <div class="v2-simple-advanced-relation">
      <V2Field
        label="Tags"
        value={filters.tagIds}
        placeholder="Tag names or IDs, comma-separated"
        disabled={filters.noTag}
        onchange={(value) => update('tagIds', value)}
      />
      <V2Checkbox
        label="No tag"
        checked={filters.noTag}
        onchange={(checked) => onchange({ ...filters, noTag: checked, tagIds: checked ? '' : filters.tagIds })}
      />
    </div>

    <V2Field label="Taken after" type="datetime-local" value={filters.takenAfter} onchange={(value) => update('takenAfter', value)} />
    <V2Field label="Taken before" type="datetime-local" value={filters.takenBefore} onchange={(value) => update('takenBefore', value)} />
    <V2Field label="Minimum width" type="number" value={filters.minWidth} placeholder="1280" onchange={(value) => update('minWidth', value)} />
    <V2Field label="Maximum width" type="number" value={filters.maxWidth} placeholder="4096" onchange={(value) => update('maxWidth', value)} />
    <V2Field label="Minimum height" type="number" value={filters.minHeight} placeholder="720" onchange={(value) => update('minHeight', value)} />
    <V2Field label="Maximum height" type="number" value={filters.maxHeight} placeholder="2160" onchange={(value) => update('maxHeight', value)} />
    <V2Field label="Minimum aspect ratio" value={filters.minAspectRatio} placeholder="16:9 or 1.778" onchange={(value) => update('minAspectRatio', value)} />
    <V2Field label="Maximum aspect ratio" value={filters.maxAspectRatio} placeholder="4:3 or 1.333" onchange={(value) => update('maxAspectRatio', value)} />
  </div>
</details>

<style>
  .v2-simple-advanced {
    overflow: visible;
    border: 1px solid var(--v2-line);
    border-radius: var(--v2-radius-sm);
    background: var(--v2-surface-2);
  }

  summary {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: .6rem;
    min-height: 2.55rem;
    padding: .55rem .65rem;
    cursor: pointer;
    list-style: none;
  }

  summary::-webkit-details-marker { display: none; }
  summary:hover { background: color-mix(in srgb, currentColor 5%, transparent); }
  summary:focus-visible { outline: 2px solid var(--v2-accent); outline-offset: -2px; }

  .v2-simple-advanced-title { font-size: .78rem; font-weight: 800; color: var(--v2-accent); }
  .v2-simple-advanced-summary { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: .75rem; color: var(--v2-muted); }
  .v2-simple-advanced-marker { display: grid; place-items: center; width: 1.55rem; height: 1.55rem; border: 1px solid var(--v2-line); border-radius: 999px; font-weight: 800; }
  details[open] .v2-simple-advanced-marker { transform: rotate(45deg); }

  .v2-simple-advanced-fields {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: .7rem;
    padding: .75rem;
    border-top: 1px solid var(--v2-line);
    background: var(--v2-surface);
  }

  .v2-simple-advanced-relation { display: grid; gap: .45rem; align-content: start; }

  @media (max-width: 62rem) {
    .v2-simple-advanced-fields { grid-template-columns: 1fr; }
    .v2-simple-advanced-summary { white-space: normal; }
  }
</style>
