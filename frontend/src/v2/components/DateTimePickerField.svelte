<script lang="ts">
  import type { ComponentProps } from 'svelte';
  import DateTimePickerField from '../../lib/components/ui/DateTimePickerField.svelte';

  let { value = $bindable(''), ...props }: ComponentProps<typeof DateTimePickerField> = $props();
</script>

<DateTimePickerField {...props} bind:value />
