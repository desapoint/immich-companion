export function resolveStackPrimary(
  stackAssetIds: readonly string[],
  requestedAssetId: string | null,
  preferredAssetIds: readonly (string | null)[] = [],
): string | null {
  const stackIds = new Set(stackAssetIds);
  if (requestedAssetId && stackIds.has(requestedAssetId)) return requestedAssetId;
  return preferredAssetIds.find((assetId): assetId is string => Boolean(assetId && stackIds.has(assetId)))
    ?? stackAssetIds[0]
    ?? null;
}
