const POSITIVE_DECIMAL = /^(?:\d+(?:\.\d*)?|\.\d+)$/;

function parsePositiveDecimal(value: string): number {
  if (!POSITIVE_DECIMAL.test(value)) throw new Error('Use a positive decimal or fraction.');
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error('Aspect ratio values must be greater than zero.');
  }
  return parsed;
}

export function parseAspectRatioInput(value: string): number {
  const normalized = value.trim();
  const parts = normalized.split('/').map((part) => part.trim());
  if (parts.length === 1) return parsePositiveDecimal(parts[0]);
  if (parts.length !== 2) throw new Error('Use one fraction slash, for example 16/9.');
  const numerator = parsePositiveDecimal(parts[0]);
  const denominator = parsePositiveDecimal(parts[1]);
  return numerator / denominator;
}

export function aspectRatioValidationMessage(value: string): string {
  if (!value.trim()) return '';
  try {
    parseAspectRatioInput(value);
    return '';
  } catch (error) {
    return error instanceof Error ? error.message : 'Enter a valid aspect ratio.';
  }
}
