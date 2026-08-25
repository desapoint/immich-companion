<script lang="ts">
  import SelectField from '../../../lib/components/ui/SelectField.svelte';
  import type { AssetCardInlineTagMode } from '../types/assets';

  interface Props {
    inlineTagMode: AssetCardInlineTagMode;
    searchedTagCount: number;
    onchange: (mode: AssetCardInlineTagMode) => void;
  }

  let { inlineTagMode, searchedTagCount, onchange }: Props = $props();
</script>

<div class="display-settings" aria-label="Card display settings">
  <SelectField
    id="card-inline-tag-mode"
    label="Inline card tags"
    value={inlineTagMode}
    options={[
      { value: 'hidden', label: 'Hidden' },
      { value: 'matching', label: `Search tags only (${searchedTagCount})` },
      { value: 'compact', label: 'First 3 tags' },
    ]}
    compact
    onchange={(value) => onchange(value as AssetCardInlineTagMode)}
  />
</div>

<style>
  .display-settings {
    width: min(14rem, 100%);
  }
</style>
