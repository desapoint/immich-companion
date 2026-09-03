<script lang="ts">
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';

  let tab = $state('Endpoints');
  let selected = $state('GET /status');
  const endpoints = [['GET','/status','Read current health and capabilities'],['POST','/assets/search','Search assets'],['POST','/duplicates/scan','Start duplicate similarity analysis'],['GET','/tasks/{id}','Read background task state']] as const;
</script>

<V2PageLayout title="API Docs" description="Developer-facing API documentation. This is not an operational Companion workflow.">
  {#snippet headerActions()}<button class="v2-button v2-button-primary">Open schema</button>{/snippet}
  {#snippet tabs()}<V2Tabs items={['Endpoints','Schemas']} active={tab} onselect={(v) => tab = v}/>{/snippet}
  {#snippet context()}<V2Zone label="Context rail"><V2Section title="Resources"><V2Stack gap="xs">{#each ['Status','Assets','Relations','Duplicates','Settings','Tasks'] as item}<button class="v2-nav-button" class:active={item==='Status'}>{item}</button>{/each}</V2Stack></V2Section></V2Zone>{/snippet}

  <V2Zone>
    <V2Toolbar label="Primary content" sticky={false}><b>API reference</b></V2Toolbar>
    <div class="v2-docs">
      <V2Card><V2Stack gap="sm"><h2 class="v2-card-title">Companion API</h2><span class="v2-muted">Developer documentation surface presented inside the same global shell for navigation consistency.</span></V2Stack></V2Card>
      {#each endpoints as endpoint}<V2Card><V2Stack gap="sm"><V2Inline gap="sm"><V2Badge tone={endpoint[0]==='GET'?'ok':'warn'} text={endpoint[0]}/><code>{endpoint[1]}</code></V2Inline><span class="v2-muted">{endpoint[2]}</span><button class="v2-button" onclick={() => selected = `${endpoint[0]} ${endpoint[1]}`}>Expand endpoint</button></V2Stack></V2Card>{/each}
    </div>
  </V2Zone>

  {#snippet inspector()}<V2Zone label="Inspector"><V2Section title="Selected endpoint"><V2Card><V2Stack gap="sm"><b>{selected}</b><span class="v2-small v2-muted">Response schema, parameters and example payload would appear here.</span></V2Stack></V2Card></V2Section></V2Zone>{/snippet}
</V2PageLayout>
