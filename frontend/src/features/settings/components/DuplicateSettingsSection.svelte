<script lang="ts">
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2ImmichDuplicateSyncSettings from '../../../v2/components/V2ImmichDuplicateSyncSettings.svelte';
  import V2Notice from '../../../lib/components/ui/Notice.svelte';
  import V2SimilarityRuntimeSettings from '../../../v2/components/V2SimilarityRuntimeSettings.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
</script>

<V2Stack gap="md">
  <V2ImmichDuplicateSyncSettings />
  <V2SimilarityRuntimeSettings />
  <V2Card title="Duplicate policy">
    {#snippet actions()}<V2Badge tone="warn" text="Policy UI pending" />{/snippet}
    <V2Notice tone="info">Immich duplicate synchronization is live. The remaining duplicate policy controls will move into this section separately.</V2Notice>
  </V2Card>
</V2Stack>
