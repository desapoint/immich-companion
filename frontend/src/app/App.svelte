<script lang="ts">
  import { errorMessage } from '../lib/utils/errors';
  import AppRuntimeError from './components/AppRuntimeError.svelte';
  import ApplicationPage from './ApplicationPage.svelte';
</script>

<svelte:boundary>
  <ApplicationPage />

  {#snippet failed(error, reset)}
    <AppRuntimeError message={errorMessage(error)} onretry={reset} />
  {/snippet}
</svelte:boundary>
