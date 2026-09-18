export function comparisonTargetId(
  ids: string[],
  referenceId: string,
  requestedId: string,
): string {
  if (requestedId !== referenceId && ids.includes(requestedId)) return requestedId;
  const referenceIndex = ids.indexOf(referenceId);
  if (referenceIndex < 0) return ids.find((id) => id !== referenceId) ?? requestedId;
  for (let offset = 1; offset < ids.length; offset += 1) {
    const candidate = ids[(referenceIndex + offset) % ids.length];
    if (candidate !== referenceId) return candidate;
  }
  return referenceId;
}

export function viewerSelectionTargetId(
  ids: string[],
  requestedId: string,
): string {
  if (ids.includes(requestedId)) return requestedId;
  return ids[0] ?? requestedId;
}

export function stepComparisonTargetId(
  ids: string[],
  referenceId: string,
  visibleId: string,
  direction: 'previous' | 'next',
): string {
  if (ids.length < 2) return ids[0] ?? visibleId;
  const start = ids.indexOf(visibleId);
  const origin = start >= 0 ? start : ids.indexOf(referenceId);
  const step = direction === 'next' ? 1 : -1;
  for (let offset = 1; offset < ids.length; offset += 1) {
    const candidate = ids[(origin + step * offset + ids.length * 2) % ids.length];
    if (candidate !== referenceId) return candidate;
  }
  return visibleId;
}
