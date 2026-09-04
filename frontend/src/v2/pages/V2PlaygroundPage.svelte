<script lang="ts">
  import SelectField from '../components/SelectField.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Modal from '../components/V2Modal.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Progress from '../components/V2Progress.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Segmented from '../components/V2Segmented.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2Toggle from '../components/V2Toggle.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2Zone from '../components/V2Zone.svelte';

  const shortOptions = ['One', 'Two', 'Three'];
  const longOptions = [
    { value: 'short', label: 'Short' },
    { value: 'long', label: 'A deliberately very long option label that should stay readable without collapsing into one-character lines' },
    { value: 'longer', label: 'Another long option intended to force intrinsic popup width and viewport clamping behavior' },
  ];
  const subtitleOptions = [
    { value: 'family', label: 'Family', subtitle: 'People / Family · 430 assets' },
    { value: 'montreal', label: 'Montréal', subtitle: 'Places / Canada / Québec / Montréal · 84 assets' },
    { value: 'project', label: 'Immich Companion', subtitle: 'Projects / Immich Companion · 892 assets' },
    { value: 'disabled', label: 'Disabled option', subtitle: 'Used to test disabled-row behavior', disabled: true },
  ];
  const manyOptions = Array.from({ length: 40 }, (_, index) => ({
    value: `option-${index + 1}`,
    label: `Option ${String(index + 1).padStart(2, '0')}`,
    subtitle: index % 3 === 0 ? `Longer subtitle for scroll and width testing · group ${Math.floor(index / 3) + 1}` : '',
  }));

  let modalOpen = $state(false);
  let edgeProbes = $state(false);
  let shortValue = $state('One');
  let longValue = $state('short');
  let subtitleValue = $state('family');
  let searchableValue = $state('montreal');
  let manyValue = $state('option-20');
  let emptyValue = $state('');
  let modalSelectValue = $state('family');
  let segment = $state('Second');
  let tab = $state('One');
  let checked = $state(true);
  let toggled = $state(false);
  let edgeValues = $state<Record<string, string>>({
    tl: 'family', tr: 'montreal', bl: 'project', br: 'family', lm: 'short', rm: 'option-20',
  });

  function setEdgeValue(key: string, value: string): void {
    edgeValues = { ...edgeValues, [key]: value };
  }
</script>

<V2PageLayout title="Playground" description="Exercise shared V2 primitives, overlay behavior, custom-select positioning and edge cases without touching live backend state.">
  {#snippet headerActions()}
    <V2Inline gap="sm" wrap={true}>
      <V2Button onclick={() => modalOpen = true} variant="primary">Open draggable popup</V2Button>
      <V2Button active={edgeProbes} onclick={() => edgeProbes = !edgeProbes}>{edgeProbes ? 'Hide' : 'Show'} viewport edge probes</V2Button>
    </V2Inline>
  {/snippet}

  {#snippet context()}
    <V2Zone>
      <V2Section title="Playground controls">
        <V2Stack gap="sm">
          <V2Button variant="primary" block={true} onclick={() => modalOpen = true}>Open draggable popup</V2Button>
          <V2Toggle label="Viewport edge probes" checked={edgeProbes} onchange={(value) => edgeProbes = value}/>
          <span class="v2-small v2-muted">The popup can be dragged to any viewport edge. Edge probes place real SelectField triggers directly against the viewport boundaries.</span>
        </V2Stack>
      </V2Section>
      <V2Section title="What to inspect">
        <V2Card>
          <V2Stack gap="xs">
            <span class="v2-small">• popup direction above/below</span>
            <span class="v2-small">• left/right viewport clamping</span>
            <span class="v2-small">• intrinsic popup width</span>
            <span class="v2-small">• long-label wrapping</span>
            <span class="v2-small">• subtitle/search/scroll behavior</span>
            <span class="v2-small">• focus, keyboard, hover and disabled states</span>
          </V2Stack>
        </V2Card>
      </V2Section>
    </V2Zone>
  {/snippet}

  <V2Zone>
    <V2Toolbar sticky={false}>
      <V2Inline gap="sm" wrap={true}>
        <V2Badge text="Shared primitives" />
        <V2Badge text="No backend calls" tone="ok" />
      </V2Inline>
    </V2Toolbar>

    <div class="v2-playground-grid">
      <V2Card title="Select · short labels">
        <V2Stack gap="sm">
          <SelectField id="playground-short" label="Short options" bind:value={shortValue} options={shortOptions} />
          <SelectField id="playground-short-content" label="Content width" bind:value={shortValue} options={shortOptions} width="content" />
          <span class="v2-small v2-muted">Selected: {shortValue}</span>
        </V2Stack>
      </V2Card>

      <V2Card title="Select · long text">
        <V2Stack gap="sm">
          <SelectField id="playground-long" label="Long option labels" bind:value={longValue} options={longOptions} />
          <SelectField id="playground-long-content" label="Long + content width" bind:value={longValue} options={longOptions} width="content" />
          <span class="v2-small v2-muted">Watch popup width, viewport clamp and ellipsis behavior.</span>
        </V2Stack>
      </V2Card>

      <V2Card title="Select · subtitles">
        <V2Stack gap="sm">
          <SelectField id="playground-subtitle" label="Rich options" bind:value={subtitleValue} options={subtitleOptions} />
          <span class="v2-small v2-muted">Includes long hierarchy paths and a disabled option.</span>
        </V2Stack>
      </V2Card>

      <V2Card title="Select · searchable">
        <V2Stack gap="sm">
          <SelectField id="playground-searchable" label="Search label or subtitle" bind:value={searchableValue} options={subtitleOptions} searchable={true} searchPlaceholder="Search labels and hierarchy paths…" />
          <span class="v2-small v2-muted">Try “Québec”, “Projects”, and “assets”.</span>
        </V2Stack>
      </V2Card>

      <V2Card title="Select · scrolling list">
        <V2Stack gap="sm">
          <SelectField id="playground-many" label="40 options" bind:value={manyValue} options={manyOptions} searchable={true} />
          <span class="v2-small v2-muted">Selected item starts around the middle so opening can test active-item scrolling.</span>
        </V2Stack>
      </V2Card>

      <V2Card title="Select · empty / disabled">
        <V2Stack gap="sm">
          <SelectField id="playground-empty" label="Clearable select" bind:value={emptyValue} options={shortOptions} allowEmpty={true} placeholder="No selection" />
          <SelectField id="playground-disabled" label="Disabled select" value="Two" options={shortOptions} disabled={true} />
        </V2Stack>
      </V2Card>

      <V2Card title="Buttons / state">
        <V2Stack gap="sm">
          <V2Inline gap="sm" wrap={true}>
            <V2Button>Default</V2Button>
            <V2Button variant="primary">Primary</V2Button>
            <V2Button variant="danger">Danger</V2Button>
            <V2Button active={true}>Active</V2Button>
            <V2Button disabled={true}>Disabled</V2Button>
          </V2Inline>
          <V2Button block={true}>Block button with a deliberately longer label for wrapping and width testing</V2Button>
        </V2Stack>
      </V2Card>

      <V2Card title="Checkbox / toggle / segmented">
        <V2Stack gap="sm">
          <V2Checkbox label="Checkbox" checked={checked} onchange={(value) => checked = value}/>
          <V2Checkbox label="Disabled checkbox" checked={true} disabled={true}/>
          <V2Toggle label="Toggle" checked={toggled} onchange={(value) => toggled = value}/>
          <V2Segmented items={['First', 'Second', 'A much longer third option']} active={segment} onselect={(value) => segment = value} ariaLabel="Playground segmented control" />
        </V2Stack>
      </V2Card>

      <V2Card title="Fields">
        <V2Stack gap="sm">
          <V2Field label="Text field" value="Editable value" />
          <V2Field label="Number field" type="number" value="42" />
          <V2Field label="Disabled field" value="Disabled value" disabled={true} />
          <V2Field label="Multiline field" multiline={true} value="Use this to test textarea height, wrapping and focus behavior." />
        </V2Stack>
      </V2Card>

      <V2Card title="Tabs / badges / progress">
        <V2Stack gap="md">
          <V2Tabs items={['One', 'Two', 'A longer tab label']} active={tab} onselect={(value) => tab = value} ariaLabel="Playground tabs" />
          <V2Inline gap="sm" wrap={true}>
            <V2Badge text="Default" />
            <V2Badge text="Healthy" tone="ok" />
            <V2Badge text="Warning" tone="warn" />
            <V2Badge text="Problem" tone="bad" />
          </V2Inline>
          <V2Progress value={62} label="Determinate playground progress" />
          <V2Progress indeterminate={true} label="Indeterminate playground progress" />
        </V2Stack>
      </V2Card>
    </div>
  </V2Zone>

  {#snippet inspector()}
    <V2Zone>
      <V2Section title="Current state">
        <V2Card>
          <V2Stack gap="xs">
            <span class="v2-small">short: <b>{shortValue}</b></span>
            <span class="v2-small">long: <b>{longValue}</b></span>
            <span class="v2-small">subtitle: <b>{subtitleValue}</b></span>
            <span class="v2-small">searchable: <b>{searchableValue}</b></span>
            <span class="v2-small">many: <b>{manyValue}</b></span>
            <span class="v2-small">empty: <b>{emptyValue || '∅'}</b></span>
          </V2Stack>
        </V2Card>
      </V2Section>
      <V2Section title="Popup testing">
        <V2Card><span class="v2-small v2-muted">Open the draggable popup and move it flush against each screen edge, then open its select. Use viewport edge probes for exact fixed trigger positions.</span></V2Card>
      </V2Section>
    </V2Zone>
  {/snippet}
</V2PageLayout>

{#if modalOpen}
  <V2Modal
    id="playground-modal"
    title="Primitive popup playground"
    description="Drag this dialog to any viewport edge or corner, then exercise the controls inside it."
    size="md"
    onclose={() => modalOpen = false}
  >
    <V2Stack gap="md">
      <V2Card>
        <V2Stack gap="sm">
          <SelectField id="playground-modal-select" label="Select inside draggable popup" bind:value={modalSelectValue} options={subtitleOptions} searchable={true} allowEmpty={true} placeholder="Choose an option" />
          <SelectField id="playground-modal-long" label="Long text inside popup" value="long" options={longOptions} />
          <SelectField id="playground-modal-many" label="Scrolling popup inside popup" value="option-20" options={manyOptions} searchable={true} />
        </V2Stack>
      </V2Card>
      <V2Card>
        <V2Stack gap="sm">
          <V2Field label="Text input in popup" value="Focus and tab-order test" />
          <V2Checkbox label="Checkbox in popup" checked={true}/>
          <V2Segmented items={['One', 'Two', 'Three']} active="Two" ariaLabel="Popup segmented control" />
        </V2Stack>
      </V2Card>
    </V2Stack>
    {#snippet footer()}
      <V2Button onclick={() => modalOpen = false}>Close</V2Button>
      <V2Button variant="primary">Primary action</V2Button>
    {/snippet}
  </V2Modal>
{/if}

{#if edgeProbes}
  <div class="v2-playground-edge-probe v2-playground-edge-tl">
    <span>top-left</span>
    <SelectField id="playground-edge-tl" width="content" value={edgeValues.tl} options={subtitleOptions} onchange={(value) => setEdgeValue('tl', value)} />
  </div>
  <div class="v2-playground-edge-probe v2-playground-edge-tr">
    <span>top-right</span>
    <SelectField id="playground-edge-tr" width="content" value={edgeValues.tr} options={longOptions} onchange={(value) => setEdgeValue('tr', value)} />
  </div>
  <div class="v2-playground-edge-probe v2-playground-edge-bl">
    <span>bottom-left</span>
    <SelectField id="playground-edge-bl" width="content" value={edgeValues.bl} options={subtitleOptions} onchange={(value) => setEdgeValue('bl', value)} />
  </div>
  <div class="v2-playground-edge-probe v2-playground-edge-br">
    <span>bottom-right</span>
    <SelectField id="playground-edge-br" width="content" value={edgeValues.br} options={subtitleOptions} searchable={true} onchange={(value) => setEdgeValue('br', value)} />
  </div>
  <div class="v2-playground-edge-probe v2-playground-edge-lm">
    <span>left edge</span>
    <SelectField id="playground-edge-lm" width="content" value={edgeValues.lm} options={longOptions} onchange={(value) => setEdgeValue('lm', value)} />
  </div>
  <div class="v2-playground-edge-probe v2-playground-edge-rm">
    <span>right edge</span>
    <SelectField id="playground-edge-rm" width="content" value={edgeValues.rm} options={manyOptions} searchable={true} onchange={(value) => setEdgeValue('rm', value)} />
  </div>
{/if}
