import { createApiLibraryDataSource } from './api/apiLibraryDataSource.svelte';
import type { ResolvedLibraryDataSource } from './contracts';
import type { LiveLibraryDataSource } from './liveContracts';

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

function withDestructiveActionGuard<T extends ResolvedLibraryDataSource>(source: T): T {
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
      applyDecisions: async (resolution) => {
        if (Object.values(resolution.decisions).includes('delete')) await requireDestructiveActions();
        return source.duplicates.applyDecisions(resolution);
      },
    },
  } as T;
}

// Single production composition point for the V2 UI. A V2 operation is live only when
// createApiLibraryDataSource explicitly implements it. Unsupported operations fail closed
// with V2NotImplementedError rather than falling back to demo data or an existing V1 API.
export const libraryData: LiveLibraryDataSource = withDestructiveActionGuard(
  createApiLibraryDataSource(),
);
