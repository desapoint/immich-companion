<script lang="ts">
  import type { SimilarityValidationMode } from '../data/contracts';
  import SelectField from './SelectField.svelte';
  import V2Stack from './V2Stack.svelte';

  let { mode, onchange }: {
    mode: SimilarityValidationMode;
    onchange: (mode: SimilarityValidationMode) => void;
  } = $props();

  const labels = ['Reference only', 'Linked group', 'Strict all-pairs'];
  const labelByMode: Record<SimilarityValidationMode, string> = {
    reference: 'Reference only',
    linked: 'Linked group',
    strict: 'Strict all-pairs',
  };
  const modeByLabel: Record<string, SimilarityValidationMode> = {
    'Reference only': 'reference',
    'Linked group': 'linked',
    'Strict all-pairs': 'strict',
  };
  const descriptions: Record<SimilarityValidationMode, string> = {
    reference: 'Each member must meet the threshold against the stable discovery anchor.',
    linked: 'Members may qualify through an accepted member; the admitting relationship is retained.',
    strict: 'Every member must meet the threshold against every other member in its review group.',
  };
</script>

<V2Stack gap="xs">
  <SelectField
    id="duplicate-validation-mode"
    label="Group validation"
    value={labelByMode[mode]}
    options={labels}
    onchange={(value) => onchange(modeByLabel[value] ?? 'strict')}
  />
  <span class="v2-small v2-muted">{descriptions[mode]}</span>
</V2Stack>
