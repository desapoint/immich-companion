import { createDemoLibraryDataSource } from './demo/demoLibraryDataSource.svelte';
import { withDemoMediaProfiles } from './demo/demoMediaProfile';
import { withDemoSavedSearches } from './demo/demoSavedSearches';
import type { ResolvedLibraryDataSource } from './contracts';

type CapabilityResponse = { destructive_actions?: boolean };

let destructiveCapabilityPromise: Promise<boolean> | null = null;

export function destructiveActionsEnabled(): Promise<boolean> {
  destructiveCapabilityPromise ??= fetch('/api/capabilities', {
    headers: { accept: 'application/json' },
  })
    .then(async (response) => {
      if (!response.ok) return false;
      const payload = (await response.json()) as CapabilityResponse;
      return payload.destructive_actions === true;
    })
    .catch(() => false);
  return destructiveCapabilityPromise;
}

async function requireDestructiveActions(): Promise<void> {
  if (await destructiveActionsEnabled()) return;
  throw new Error('Destructive actions are disabled by ALLOW_DESTRUCTIVE_ACTIONS.');
}

function withDestructiveActionGuard(source: ResolvedLibraryDataSource): ResolvedLibraryDataSource {
  return {
    ...source,
    assets: {
      ...source.assets,
      trash: async (target) => {
        await requireDestructiveActions();
        return source.assets.trash(target);
      },
    },
    duplicates: {
      ...source.duplicates,
      applyDecisions: async (decisions) => {
        if (Object.values(decisions).includes('delete')) await requireDestructiveActions();
        return source.duplicates.applyDecisions(decisions);
      },
    },
  };
}

// Single composition point for the V2 UI. Replacing this with an API-backed
// implementation should not require page/component changes.
const demoLibraryData = withDemoSavedSearches(withDemoMediaProfiles(createDemoLibraryDataSource()));
export const libraryData = withDestructiveActionGuard(demoLibraryData);
