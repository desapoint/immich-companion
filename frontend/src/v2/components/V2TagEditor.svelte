<script lang="ts">
  import SelectField, { type SelectOption } from './SelectField.svelte';
  import V2Button from './V2Button.svelte';
  import V2Card from './V2Card.svelte';
  import V2Field from './V2Field.svelte';
  import V2Inline from './V2Inline.svelte';
  import V2Stack from './V2Stack.svelte';

  let {
    mode,
    name = '',
    color = '#9A78FF',
    parent = '',
    parentOptions = [],
    onsave,
    oncancel,
  }: {
    mode: 'create' | 'edit';
    name?: string;
    color?: string;
    parent?: string;
    parentOptions?: SelectOption[];
    onsave?: (value: { name: string; color: string; parent: string }) => void;
    oncancel?: () => void;
  } = $props();

  let draftName = $state(name);
  let draftColor = $state(color);
  let draftParent = $state(parent);

  $effect(() => {
    draftName = name;
    draftColor = color;
    draftParent = parent;
  });
</script>

<V2Card>
  <V2Stack gap="sm">
    <p class="v2-text-block v2-small v2-muted">{mode === 'create' ? 'Create a new tag. Parent is optional.' : 'Edit this tag and its parent relationship.'}</p>
    <V2Field label="Name" value={draftName} onchange={(value) => (draftName = value)} />
    <V2Field label="Color" value={draftColor} onchange={(value) => (draftColor = value)} />
    <SelectField
      id={`tag-parent-${mode}`}
      label="Parent"
      bind:value={draftParent}
      options={parentOptions}
      allowEmpty={true}
      searchable={true}
      searchPlaceholder="Search parent tags or paths…"
      placeholder="No parent — root tag"
    />
    <V2Inline gap="sm">
      <V2Button onclick={oncancel}>Cancel</V2Button>
      <V2Button variant="primary" onclick={() => onsave?.({ name: draftName, color: draftColor, parent: draftParent })}>
        {mode === 'create' ? 'Create tag' : 'Save changes'}
      </V2Button>
    </V2Inline>
  </V2Stack>
</V2Card>
