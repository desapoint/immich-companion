import { demoAssetState, type DemoAssetStackSnapshot } from './demoAssetState.svelte';

export function normalizeDemoStacks(): void {
  const byStack = new Map<string, string[]>();
  for (const asset of demoAssetState.assets) {
    if (!asset.stack) continue;
    const members = byStack.get(asset.stack.id) ?? [];
    members.push(asset.id);
    byStack.set(asset.stack.id, members);
  }

  for (const [stackId, memberIds] of byStack) {
    const members = [...new Set(memberIds)];
    if (members.length < 2) {
      for (const asset of demoAssetState.assets) if (asset.stack?.id === stackId) asset.stack = null;
      continue;
    }

    const existingPrimary = demoAssetState.assets.find((asset) => asset.stack?.id === stackId)?.stack?.primaryAssetId;
    const primaryAssetId = existingPrimary && members.includes(existingPrimary) ? existingPrimary : members[0];
    const normalized: DemoAssetStackSnapshot = { id: stackId, primaryAssetId, assetCount: members.length, assets: members };
    for (const asset of demoAssetState.assets) if (asset.stack?.id === stackId) asset.stack = { ...normalized, assets: [...members] };
  }
}
