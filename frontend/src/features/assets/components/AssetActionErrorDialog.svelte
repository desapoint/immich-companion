<script lang="ts">
  import ConfirmDialog from '../../../lib/components/ui/ConfirmDialog.svelte';

  interface Props {
    message: string;
    onclose: () => void;
  }

  let { message, onclose }: Props = $props();
</script>

<ConfirmDialog
  title="Action could not be completed"
  {message}
  confirmLabel="Close"
  icon="info"
  onconfirm={onclose}
  {onclose}
/>
