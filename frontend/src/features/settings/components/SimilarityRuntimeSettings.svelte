<script lang="ts">
  import { onMount } from 'svelte';

  import { jsonRequest, requestJson } from '../../../lib/api/http';
  import V2Badge from '../../../lib/components/ui/Badge.svelte';
  import V2Button from '../../../lib/components/ui/Button.svelte';
  import V2Card from '../../../lib/components/ui/Card.svelte';
  import V2Field from '../../../lib/components/ui/TextField.svelte';
  import V2Notice from '../../../lib/components/ui/Notice.svelte';
  import V2Stack from '../../../lib/components/layout/Stack.svelte';

  type ApiSimilarityRuntimeSettings = {
    fingerprint_page_size: number;
  };

  let pageSize = $state<number | null>(null);
  let savedPageSize = $state<number | null>(null);
  let loading = $state(true);
  let saving = $state(false);
  let error = $state('');
  let success = $state('');

  const dirty = $derived(pageSize !== null && savedPageSize !== null && pageSize !== savedPageSize);
  const valid = $derived(pageSize !== null && Number.isInteger(pageSize) && pageSize >= 25 && pageSize <= 2000);

  async function load(): Promise<void> {
    loading = true;
    error = '';
    try {
      const settings = await requestJson<ApiSimilarityRuntimeSettings>(
        '/api/settings/duplicates/similarity-runtime',
      );
      pageSize = settings.fingerprint_page_size;
      savedPageSize = settings.fingerprint_page_size;
    } catch (value) {
      error = value instanceof Error ? value.message : 'Similarity runtime settings could not be loaded.';
    } finally {
      loading = false;
    }
  }

  function setPageSize(raw: string): void {
    const value = Number(raw);
    if (!Number.isFinite(value)) return;
    pageSize = Math.trunc(value);
    success = '';
  }

  async function save(): Promise<void> {
    if (!dirty || !valid || pageSize === null || saving) return;
    saving = true;
    error = '';
    success = '';
    try {
      const settings = await requestJson<ApiSimilarityRuntimeSettings>(
        '/api/settings/duplicates/similarity-runtime',
        jsonRequest('PUT', { fingerprint_page_size: pageSize }),
      );
      pageSize = settings.fingerprint_page_size;
      savedPageSize = settings.fingerprint_page_size;
      success = 'Similarity fingerprint runtime settings saved.';
    } catch (value) {
      error = value instanceof Error ? value.message : 'Similarity runtime settings could not be saved.';
    } finally {
      saving = false;
    }
  }

  onMount(() => {
    void load();
  });
</script>

<V2Card title="Similarity fingerprinting">
  {#snippet actions()}
    {#if pageSize !== null}
      <V2Badge tone={dirty ? 'warn' : 'ok'} text={dirty ? 'Unsaved changes' : 'Saved'} />
    {/if}
  {/snippet}

  <V2Stack gap="sm">
    <span class="v2-small v2-muted">
      Tune how much fingerprint work is selected from PostgreSQL at once. This does not increase preview fetch or image decode concurrency.
    </span>

    {#if loading}
      <V2Notice>Loading similarity fingerprint runtime settings…</V2Notice>
    {:else if pageSize !== null}
      <V2Field
        label="Fingerprint database page size"
        type="number"
        min="25"
        max="2000"
        step="25"
        value={pageSize}
        onchange={setPageSize}
      />
      <span class="v2-small v2-muted">
        Applies when the next similarity fingerprint maintenance run starts. Larger pages reduce work-selection and checkpoint overhead while the existing fetch/decode slots continue to bound active media processing.
      </span>
      {#if !valid}<V2Notice tone="warning">Choose a whole-number page size from 25 through 2000.</V2Notice>{/if}
      {#if error}<V2Notice tone="error">{error}</V2Notice>{/if}
      {#if success}<V2Notice tone="success">{success}</V2Notice>{/if}
      <div>
        <V2Button variant="primary" disabled={!dirty || !valid || saving} onclick={() => void save()}>
          {saving ? 'Saving…' : 'Save fingerprint settings'}
        </V2Button>
      </div>
    {:else}
      <V2Notice tone="error">{error || 'Similarity runtime settings are unavailable.'}</V2Notice>
      <div><V2Button onclick={() => void load()}>Retry</V2Button></div>
    {/if}
  </V2Stack>
</V2Card>
