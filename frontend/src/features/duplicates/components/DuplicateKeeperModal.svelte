<script lang="ts">
  import type { ComponentProps } from 'svelte';
  import LegacyDuplicateKeeperModal from './DuplicateKeeperLegacy.svelte';

  let props: ComponentProps<typeof LegacyDuplicateKeeperModal> = $props();
</script>

<LegacyDuplicateKeeperModal {...props} />
