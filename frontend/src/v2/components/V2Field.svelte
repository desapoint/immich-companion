<script lang="ts">
  let { label, value = '', type = 'text', options = [], placeholder = '', onchange }: { label: string; value?: string|number; type?: string; options?: string[]; placeholder?: string; onchange?: (value:string)=>void } = $props();
</script>
<label class="v2-field"><span>{label}</span>{#if options.length}<select value={String(value)} onchange={(e)=>onchange?.(e.currentTarget.value)}>{#each options as option}<option>{option}</option>{/each}</select>{:else}<input {type} value={value} {placeholder} onchange={(e)=>onchange?.(e.currentTarget.value)}>{/if}</label>
