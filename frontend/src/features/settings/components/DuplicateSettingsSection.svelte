<script lang="ts">
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2ImmichDuplicateSyncSettings from '../../duplicates/components/ImmichDuplicateSyncSettings.svelte';
  import V2Notice from '../../../lib/components/ui/Notice.svelte';
  import SimilarityRuntimeSettings from './SimilarityRuntimeSettings.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Section from '../../../lib/components/layout/Section.svelte';
</script>

<V2Stack gap="md">
  <V2Section title="Duplicate sources">
    <V2ImmichDuplicateSyncSettings />
  </V2Section>
  <V2Section title="Similarity engine">
    <SimilarityRuntimeSettings />
  </V2Section>
  <V2Section title="Duplicate policy">
    <V2Card title="Policy controls">
      {#snippet actions()}<V2Badge tone="warn" text="Coming later" />{/snippet}
      <V2Notice tone="info">Immich duplicate synchronization is live. Additional policy controls will be added here in a later release.</V2Notice>
    </V2Card>
  </V2Section>
</V2Stack>
