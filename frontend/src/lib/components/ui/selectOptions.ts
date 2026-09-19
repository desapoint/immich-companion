import type { SelectOption } from '../../types/ui';

export function firstEnabledIndex(options: readonly SelectOption[]): number {
	return options.findIndex((option) => !option.disabled);
}

export function lastEnabledIndex(options: readonly SelectOption[]): number {
	for (let index = options.length - 1; index >= 0; index -= 1) {
		if (!options[index]?.disabled) return index;
	}
	return -1;
}

export function selectedOptionIndex(options: readonly SelectOption[], value: string): number {
	const index = options.findIndex((option) => option.value === value && !option.disabled);
	return index >= 0 ? index : firstEnabledIndex(options);
}

export function adjacentEnabledIndex(options: readonly SelectOption[], start: number, direction: 1 | -1): number {
	if (!options.length) return -1;
	let index = start;
	for (let attempt = 0; attempt < options.length; attempt += 1) {
		index = (index + direction + options.length) % options.length;
		if (!options[index]?.disabled) return index;
	}
	return -1;
}

export function typeaheadIndex(options: readonly SelectOption[], query: string): number {
	return options.findIndex((option) => !option.disabled && option.label.toLocaleLowerCase().startsWith(query));
}
