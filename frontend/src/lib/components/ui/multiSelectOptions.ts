import type { SelectOption } from '../../types/ui';

export function firstEnabledOptionIndex(options: readonly SelectOption[]): number {
	return options.findIndex((option) => !option.disabled);
}

export function nextEnabledOptionIndex(
	options: readonly SelectOption[],
	start: number,
	direction: 1 | -1,
): number {
	if (!options.length) return -1;
	let index = start;
	for (let attempt = 0; attempt < options.length; attempt += 1) {
		index = (index + direction + options.length) % options.length;
		if (!options[index]?.disabled) return index;
	}
	return -1;
}

export function filterSelectOptions(
	options: readonly SelectOption[],
	query: string,
	searchable: boolean,
): SelectOption[] {
	const normalized = query.trim().toLocaleLowerCase();
	if (!searchable || !normalized) return [...options];
	return options.filter((option) => option.label.toLocaleLowerCase().includes(normalized));
}

export function canCreateSelectOption(
	options: readonly SelectOption[],
	query: string,
	allowCreate: boolean,
): boolean {
	const value = query.trim();
	return allowCreate && Boolean(value) && !options.some(
		(option) => option.label.trim().toLocaleLowerCase() === value.toLocaleLowerCase(),
	);
}
