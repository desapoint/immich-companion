<script lang="ts">
	import type { SelectOption } from '../../types/ui';

	let {
		values,
		selectedOptions,
		placeholder,
	}: {
		values: readonly string[];
		selectedOptions: readonly SelectOption[];
		placeholder: string;
	} = $props();

	const summary = $derived(
		selectedOptions.length === 0
			? placeholder
			: selectedOptions.length <= 2
				? selectedOptions.map((option) => option.label).join(', ')
				: `${selectedOptions.length} selected`,
	);
</script>

<span class:placeholder={!selectedOptions.length} class="selected-value">{summary}</span>
<span class="selection-count" aria-hidden="true">{values.length || ''}</span>

<style>
	.selected-value { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.selected-value.placeholder { color: var(--color-ink-muted); }
	.selection-count { display: grid; min-width: 1.25rem; min-height: 1.25rem; padding-inline: 0.25rem; place-items: center; border-radius: 999px; color: var(--color-accent-strong); background: var(--color-surface-soft); font-size: 0.64rem; font-weight: 800; }
	.selection-count:empty { visibility: hidden; }
</style>
