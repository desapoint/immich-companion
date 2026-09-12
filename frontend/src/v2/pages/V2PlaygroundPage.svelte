<script lang="ts">
  import DateTimePickerField from '../components/DateTimePickerField.svelte';
  import SelectField from '../components/SelectField.svelte';
  import V2Badge from '../components/V2Badge.svelte';
  import V2Button from '../components/V2Button.svelte';
  import V2Card from '../components/V2Card.svelte';
  import V2Checkbox from '../components/V2Checkbox.svelte';
  import V2ColorField from '../components/V2ColorField.svelte';
  import V2Field from '../components/V2Field.svelte';
  import V2Inline from '../components/V2Inline.svelte';
  import V2Modal from '../components/V2Modal.svelte';
  import V2Notice from '../components/V2Notice.svelte';
  import V2PageLayout from '../components/V2PageLayout.svelte';
  import V2Progress from '../components/V2Progress.svelte';
  import V2RangeSlider from '../components/V2RangeSlider.svelte';
  import V2RelationFilterField from '../components/V2RelationFilterField.svelte';
  import V2Section from '../components/V2Section.svelte';
  import V2Segmented from '../components/V2Segmented.svelte';
  import V2Stack from '../components/V2Stack.svelte';
  import V2Tabs from '../components/V2Tabs.svelte';
  import V2TaskBubble from '../components/V2TaskBubble.svelte';
  import V2Toggle from '../components/V2Toggle.svelte';
  import V2Toolbar from '../components/V2Toolbar.svelte';
  import V2VideoPlayer from '../components/V2VideoPlayer.svelte';
  import V2Zone from '../components/V2Zone.svelte';
  import { useOptionalV2Toasts, type V2ToastTone } from '../state/toasts.svelte';

  const shortOptions = ['One', 'Two', 'Three'];
  const richOptions = [
    { value: 'family', label: 'Family', subtitle: 'People / Family · 430 assets' },
    { value: 'montreal', label: 'Montréal', subtitle: 'Places / Canada / Québec / Montréal · 84 assets' },
    { value: 'project', label: 'Immich Companion', subtitle: 'Projects / Immich Companion · 892 assets' },
    { value: 'disabled', label: 'Disabled option', subtitle: 'Disabled-row behavior', disabled: true },
  ];
  const manyOptions = Array.from({ length: 40 }, (_, index) => ({
    value: `option-${index + 1}`,
    label: `Option ${String(index + 1).padStart(2, '0')}`,
    subtitle: index % 4 === 0 ? `Long subtitle for scrolling and width testing · group ${index + 1}` : '',
  }));

  let modalOpen = $state(false);
  let edgeProbes = $state(false);
  let singleValue = $state('family');
  let clearableValue = $state('');
  let multiValues = $state<string[]>(['family', 'project']);
  let relationValues = $state<string[]>(['family']);
  let relationEmpty = $state(false);
  let dateOnlyValue = $state('2026-09-06');
  let dateTimeValue = $state('2026-09-06T14:30');
  let segment = $state('Standard');
  let tab = $state('One');
  let checked = $state(true);
  let toggled = $state(false);
  let slider = $state(62);
  let modalSelect = $state('montreal');
  let color = $state<string|null>('#9A78FF');
  const toasts = useOptionalV2Toasts();

  function showToast(tone:V2ToastTone):void{
    const labels={info:'Information',success:'Action completed',warning:'Action needs review',error:'Action failed'};
    toasts?.push({tone,title:labels[tone],message:`This is a ${tone} toast from the static component playground.`});
  }
  function showToastStack():void{
    showToast('success');showToast('warning');showToast('error');
  }
</script>

<V2PageLayout title="Playground" description="Exercise shared V2 primitives, component states and overlay positioning without touching backend state.">
  {#snippet headerActions()}
    <V2Inline gap="sm" wrap>
      <V2Button variant="primary" onclick={() => modalOpen = true}>Open popup test</V2Button>
      <V2Button active={edgeProbes} onclick={() => edgeProbes = !edgeProbes}>{edgeProbes ? 'Hide' : 'Show'} edge probes</V2Button>
    </V2Inline>
  {/snippet}

  {#snippet context()}
    <V2Zone>
      <V2Section title="Coverage">
        <V2Card>
          <V2Stack gap="xs">
            <span class="v2-small">Single, searchable and multiple selects</span>
            <span class="v2-small">Relation filter exclusivity</span>
            <span class="v2-small">Date-only and 24-hour date/time picker modes</span>
            <span class="v2-small">Buttons, fields, toggles, sliders, tabs, progress, notices and modal states</span>
            <span class="v2-small">Color selection and stacked toast notifications</span>
          </V2Stack>
        </V2Card>
      </V2Section>
    </V2Zone>
  {/snippet}

  <V2Zone>
    <V2Toolbar sticky={false}>
      <V2Inline gap="sm" wrap><V2Badge text="Shared primitives"/><V2Badge text="No backend calls" tone="ok"/></V2Inline>
    </V2Toolbar>

    <div class="v2-playground-grid">
      <V2Card title="Feedback / notices">
        <V2Stack gap="sm">
          <V2Notice tone="info" title="Information">Use for neutral context, guidance, or non-blocking system information.</V2Notice>
          <V2Notice tone="success" title="Success">The operation completed successfully and no further action is required.</V2Notice>
          <V2Notice tone="warning" title="Warning">The operation can continue, but the user should understand an important condition.</V2Notice>
          <V2Notice tone="error" title="Error">The operation failed or is blocked and needs attention before continuing.</V2Notice>
        </V2Stack>
      </V2Card>

      <V2Card title="Toast notifications">
        <V2Stack gap="sm">
          <span class="v2-small v2-muted">Toasts use the corner selected in Settings → General and can stack without replacing one another.</span>
          <V2Inline gap="sm" wrap><V2Button onclick={()=>showToast('info')}>Info</V2Button><V2Button onclick={()=>showToast('success')}>Success</V2Button><V2Button onclick={()=>showToast('warning')}>Warning</V2Button><V2Button variant="danger" onclick={()=>showToast('error')}>Error</V2Button></V2Inline>
          <V2Button block onclick={showToastStack}>Show multiple toasts</V2Button>
        </V2Stack>
      </V2Card>

      <V2Card title="Color field">
        <V2Stack gap="sm"><V2ColorField id="playground-color" label="Reusable color" value={color} onchange={(value)=>color=value}/><span class="v2-small v2-muted">Selected: {color??'No color'}</span></V2Stack>
      </V2Card>

      <V2Card title="Video playback overlay">
        <div class="v2-playground-video"><V2VideoPlayer src="/demo-fixtures/clip.mp4" poster="/demo-fixtures/video-poster.jpg" label="Playground video"/></div>
      </V2Card>

      <V2Card title="Select · single / searchable">
        <V2Stack gap="sm">
          <SelectField id="playground-single" label="Rich options" bind:value={singleValue} options={richOptions} searchable searchPlaceholder="Search labels or subtitles…"/>
          <SelectField id="playground-clearable" label="Clearable" bind:value={clearableValue} options={shortOptions} allowEmpty placeholder="No selection"/>
          <SelectField id="playground-disabled" label="Disabled" value="Two" options={shortOptions} disabled/>
        </V2Stack>
      </V2Card>

      <V2Card title="Select · multiple">
        <V2Stack gap="sm">
          <SelectField id="playground-multiple" label="Multiple options" multiple searchable allowEmpty bind:values={multiValues} options={richOptions} placeholder="Choose several options"/>
          <span class="v2-small v2-muted">Selected: {multiValues.join(', ') || '∅'}</span>
        </V2Stack>
      </V2Card>

      <V2Card title="Select · long scrolling list">
        <V2Stack gap="sm">
          <SelectField id="playground-many" label="40 searchable options" value="option-20" options={manyOptions} searchable/>
          <span class="v2-small v2-muted">Tests popup clamping, scrolling, selected state and long subtitles.</span>
        </V2Stack>
      </V2Card>

      <V2Card title="Relation filter">
        <V2Stack gap="sm">
          <V2RelationFilterField
            id="playground-relation"
            label="Albums"
            values={relationValues}
            options={richOptions}
            emptySelected={relationEmpty}
            emptyLabel="No album"
            placeholder="Any album"
            onvalueschange={(values) => relationValues = values}
            onemptychange={(selected) => relationEmpty = selected}
          />
          <span class="v2-small v2-muted">State: {relationEmpty ? 'No album' : relationValues.join(', ') || 'Any album'}</span>
        </V2Stack>
      </V2Card>

      <V2Card title="Date picker · date only">
        <V2Stack gap="sm">
          <DateTimePickerField id="playground-date" label="Date only" showTime={false} bind:value={dateOnlyValue}/>
          <span class="v2-small v2-muted">Value: {dateOnlyValue || '∅'} · format YYYY-MM-DD</span>
        </V2Stack>
      </V2Card>

      <V2Card title="Date picker · 24-hour time">
        <V2Stack gap="sm">
          <DateTimePickerField id="playground-date-time" label="Date and time" showTime bind:value={dateTimeValue}/>
          <span class="v2-small v2-muted">Value: {dateTimeValue || '∅'} · time input HH:MM</span>
        </V2Stack>
      </V2Card>

      <V2Card title="Buttons / state">
        <V2Stack gap="sm">
          <V2Inline gap="sm" wrap>
            <V2Button>Default</V2Button><V2Button variant="primary">Primary</V2Button><V2Button variant="danger">Danger</V2Button><V2Button active>Active</V2Button><V2Button disabled>Disabled</V2Button>
          </V2Inline>
          <V2Button block>Block button with a longer label</V2Button>
        </V2Stack>
      </V2Card>

      <V2Card title="Checkbox / toggle / segmented">
        <V2Stack gap="sm">
          <V2Checkbox label="Checkbox" checked={checked} onchange={(value) => checked = value}/>
          <V2Toggle label="Toggle" checked={toggled} onchange={(value) => toggled = value}/>
          <V2Segmented items={['Standard','Condensed']} active={segment} onselect={(value) => segment = value} ariaLabel="Density example"/>
        </V2Stack>
      </V2Card>

      <V2Card title="Fields">
        <V2Stack gap="sm">
          <V2Field label="Text field" value="Editable value"/>
          <V2Field label="Number field" type="number" value="42"/>
          <V2Field label="Disabled field" value="Disabled value" disabled/>
          <V2Field label="Multiline" multiline value="Textarea wrapping and focus behavior."/>
        </V2Stack>
      </V2Card>

      <V2Card title="Progress / task bubble">
        <V2Stack gap="md">
          <V2Progress value={62} label="Determinate progress"/>
          <V2Progress indeterminate label="Indeterminate progress"/>
          <V2Inline gap="sm"><V2TaskBubble value={62} label="Collapsed progress" detail="Known"/><V2TaskBubble indeterminate label="Collapsed indeterminate" detail="Unknown"/></V2Inline>
        </V2Stack>
      </V2Card>

      <V2Card title="Range slider">
        <V2Stack gap="sm">
          <V2RangeSlider label="Fill" bind:value={slider} min={0} max={100} suffix="%" track="fill" ariaLabel="Playground slider"/>
          <V2RangeSlider label="Plain compact" value={5} min={0} max={10} width={120} track="plain" ariaLabel="Compact playground slider"/>
        </V2Stack>
      </V2Card>

      <V2Card title="Tabs / badges">
        <V2Stack gap="md">
          <V2Tabs items={['One','Two','Longer tab']} active={tab} onselect={(value) => tab = value} ariaLabel="Playground tabs"/>
          <V2Inline gap="sm" wrap><V2Badge text="Default"/><V2Badge text="Healthy" tone="ok"/><V2Badge text="Warning" tone="warn"/><V2Badge text="Problem" tone="bad"/></V2Inline>
        </V2Stack>
      </V2Card>
    </div>
  </V2Zone>

  {#snippet inspector()}
    <V2Zone>
      <V2Section title="Current state">
        <V2Card>
          <V2Stack gap="xs">
            <span class="v2-small">single: <b>{singleValue}</b></span>
            <span class="v2-small">multiple: <b>{multiValues.join(', ') || '∅'}</b></span>
            <span class="v2-small">date: <b>{dateOnlyValue || '∅'}</b></span>
            <span class="v2-small">date + time: <b>{dateTimeValue || '∅'}</b></span>
            <span class="v2-small">density: <b>{segment}</b></span>
          </V2Stack>
        </V2Card>
      </V2Section>
    </V2Zone>
  {/snippet}
</V2PageLayout>

{#if modalOpen}
  <V2Modal id="playground-modal" title="Popup playground" description="Exercise controls inside an overlay." size="md" onclose={() => modalOpen = false}>
    <V2Stack gap="md">
      <SelectField id="playground-modal-select" label="Select in modal" bind:value={modalSelect} options={richOptions} searchable/>
      <DateTimePickerField id="playground-modal-date" label="Date in modal" showTime={false} value={dateOnlyValue}/>
      <V2RangeSlider label="Slider in modal" value={50} min={0} max={100} suffix="%"/>
    </V2Stack>
    {#snippet footer()}<V2Button onclick={() => modalOpen = false}>Close</V2Button><V2Button variant="primary">Primary action</V2Button>{/snippet}
  </V2Modal>
{/if}

<style>.v2-playground-video{height:15rem;overflow:hidden;border:1px solid var(--v2-line);border-radius:.65rem;background:#000}</style>

{#if edgeProbes}
  <div class="v2-playground-edge-probe v2-playground-edge-tl"><span>top-left</span><SelectField id="playground-edge-tl" width="content" value="family" options={richOptions}/></div>
  <div class="v2-playground-edge-probe v2-playground-edge-br"><span>bottom-right</span><DateTimePickerField id="playground-edge-date" label="Date" showTime={false} value={dateOnlyValue}/></div>
{/if}
