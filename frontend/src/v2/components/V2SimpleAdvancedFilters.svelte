<script lang="ts">
  import V2Badge from './V2Badge.svelte';
  import V2Button from './V2Button.svelte';
  import V2Field from './V2Field.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2RelationFilterField from './V2RelationFilterField.svelte';
  import V2Section from './V2Section.svelte';
  import V2Stack from './V2Stack.svelte';
  import type { SelectOption } from './SelectField.svelte';
  import { demoAssetState } from '../demo/demoAssetState.svelte';

  export type SimpleAdvancedFilters = {
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
    albumOptions = [],
    tagOptions = [],
    onchange,
  }: {
    filters: SimpleAdvancedFilters;
    albumOptions?: SelectOption[];
    tagOptions?: SelectOption[];
    onchange: (filters: SimpleAdvancedFilters) => void;
  } = $props();

  function emptyFilters(): SimpleAdvancedFilters {
    return {
      albumIds: '',
      tagIds: '',
      noAlbum: false,
      noTag: false,
      takenAfter: '',
      takenBefore: '',
      minWidth: '',
      maxWidth: '',
      minHeight: '',
      maxHeight: '',
      minAspectRatio: '',
      maxAspectRatio: '',
    };
  }

  let open = $state(false);
  let draft = $state<SimpleAdvancedFilters>(emptyFilters());

  const splitIds = (value: string) => value.split(',').map((part) => part.trim()).filter(Boolean);
  const joinIds = (values: string[]) => values.join(',');
  const resolvedAlbumOptions = $derived(albumOptions.length > 0 ? albumOptions : demoAssetState.albums.map((album) => ({
    value: album.id,
    label: album.album_name,
    subtitle: `${album.asset_count.toLocaleString()} asset${album.asset_count === 1 ? '' : 's'}`,
  })));
  const resolvedTagOptions = $derived(tagOptions.length > 0 ? tagOptions : demoAssetState.tags.map((tag) => ({
    value: tag.id,
    label: tag.tag_name,
    subtitle: `${tag.asset_count.toLocaleString()} asset${tag.asset_count === 1 ? '' : 's'}`,
  })));

  function countActive(value: SimpleAdvancedFilters): number {
    return splitIds(value.albumIds).length
      + splitIds(value.tagIds).length
      + Number(value.noAlbum)
      + Number(value.noTag)
      + [
        value.takenAfter,
        value.takenBefore,
        value.minWidth,
        value.maxWidth,
        value.minHeight,
        value.maxHeight,
        value.minAspectRatio,
        value.maxAspectRatio,
      ].filter((entry) => entry.trim()).length;
  }

  const activeCount = $derived(countActive(filters));
  const draftActiveCount = $derived(countActive(draft));

  function show(): void {
    draft = { ...filters };
    open = true;
  }

  function cancel(): void {
    draft = { ...filters };
    open = false;
  }

  function apply(): void {
    onchange({ ...draft });
    open = false;
  }

  function update<K extends keyof SimpleAdvancedFilters>(key: K, value: SimpleAdvancedFilters[K]): void {
    draft = { ...draft, [key]: value };
  }
</script>

<svelte:window onkeydown={(event) => { if (open && event.key === 'Escape') cancel(); }}/>

<V2Button block active={activeCount > 0} onclick={show}>
  Advanced{activeCount > 0 ? ` · ${activeCount}` : ''}
</V2Button>

{#if open}
  <button type="button" class="v2-drawer-backdrop" aria-label="Close advanced filters" onclick={cancel}></button>
  <aside class="v2-drawer" aria-label="Advanced simple search filters">
    <div class="v2-drawer-head">
      <div>
        <h2>Advanced filters</h2>
        <p class="v2-muted">Filter by relationships, taken date, dimensions and aspect ratio.</p>
      </div>
      <V2Button iconOnly title="Close advanced filters" ariaLabel="Close advanced filters" onclick={cancel}>✕</V2Button>
    </div>

    <div class="v2-drawer-body">
      <V2Stack gap="md">
        <V2Section title="Relationships">
          <V2Stack gap="md">
            <V2RelationFilterField
              id="asset-advanced-albums"
              label="Albums"
              values={splitIds(draft.albumIds)}
              options={resolvedAlbumOptions}
              emptySelected={draft.noAlbum}
              emptyLabel="No album"
              placeholder="Any album"
              onvalueschange={(values) => {
                draft = { ...draft, albumIds: joinIds(values), noAlbum: values.length > 0 ? false : draft.noAlbum };
              }}
              onemptychange={(selected) => {
                draft = { ...draft, noAlbum: selected, albumIds: selected ? '' : draft.albumIds };
              }}
            />
            <V2RelationFilterField
              id="asset-advanced-tags"
              label="Tags"
              values={splitIds(draft.tagIds)}
              options={resolvedTagOptions}
              emptySelected={draft.noTag}
              emptyLabel="No tag"
              placeholder="Any tag"
              onvalueschange={(values) => {
                draft = { ...draft, tagIds: joinIds(values), noTag: values.length > 0 ? false : draft.noTag };
              }}
              onemptychange={(selected) => {
                draft = { ...draft, noTag: selected, tagIds: selected ? '' : draft.tagIds };
              }}
            />
          </V2Stack>
        </V2Section>

        <V2Section title="Taken date">
          <div class="v2-advanced-grid">
            <V2Field label="Taken after" type="datetime-local" value={draft.takenAfter} onchange={(value) => update('takenAfter', value)} />
            <V2Field label="Taken before" type="datetime-local" value={draft.takenBefore} onchange={(value) => update('takenBefore', value)} />
          </div>
        </V2Section>

        <V2Section title="Dimensions">
          <div class="v2-advanced-grid">
            <V2Field label="Minimum width" type="number" value={draft.minWidth} placeholder="1280" onchange={(value) => update('minWidth', value)} />
            <V2Field label="Maximum width" type="number" value={draft.maxWidth} placeholder="4096" onchange={(value) => update('maxWidth', value)} />
            <V2Field label="Minimum height" type="number" value={draft.minHeight} placeholder="720" onchange={(value) => update('minHeight', value)} />
            <V2Field label="Maximum height" type="number" value={draft.maxHeight} placeholder="2160" onchange={(value) => update('maxHeight', value)} />
          </div>
        </V2Section>

        <V2Section title="Aspect ratio">
          <div class="v2-advanced-grid">
            <V2Field label="Minimum aspect ratio" value={draft.minAspectRatio} placeholder="16:9 or 1.778" onchange={(value) => update('minAspectRatio', value)} />
            <V2Field label="Maximum aspect ratio" value={draft.maxAspectRatio} placeholder="4:3 or 1.333" onchange={(value) => update('maxAspectRatio', value)} />
          </div>
        </V2Section>
      </V2Stack>
    </div>

    <div class="v2-drawer-foot">
      <V2Badge text={draftActiveCount > 0 ? `${draftActiveCount} active` : 'No advanced filters'}/>
      <V2Inline gap="sm">
        <V2Button onclick={() => draft = emptyFilters()}>Reset</V2Button>
        <V2Button onclick={cancel}>Cancel</V2Button>
        <V2Button variant="primary" onclick={apply}>Apply</V2Button>
      </V2Inline>
    </div>
  </aside>
{/if}

<style>
  .v2-advanced-grid {
    display:grid;
    grid-template-columns:repeat(2,minmax(0,1fr));
    gap:.7rem;
  }

  @media (max-width: 42rem) {
    .v2-advanced-grid { grid-template-columns:1fr; }
  }
</style>
