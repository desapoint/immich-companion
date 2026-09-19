<script lang="ts">
  import type { ComponentProps } from 'svelte';
  import LegacyDuplicateKeeperModal from '../../../v2/components/V2DuplicateKeeperModal.svelte';

  let props: ComponentProps<typeof LegacyDuplicateKeeperModal> = $props();
</script>

<LegacyDuplicateKeeperModal {...props} />
