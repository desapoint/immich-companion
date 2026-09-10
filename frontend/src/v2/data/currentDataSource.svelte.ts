import { destructiveActionAvailability, type CapabilityAvailability } from '../../lib/api/capabilities';
import { createApiLibraryDataSource } from './api/apiLibraryDataSource.svelte';
import type { ResolvedLibraryDataSource } from './contracts';
import type { LiveLibraryDataSource } from './liveContracts';

let destructiveCapabilityPromise: Promise<CapabilityAvailability> | null = null;

export function destructiveActionsAvailability(): Promise<CapabilityAvailability> {
  destructiveCapabilityPromise ??= destructiveActionAvailability();
  return destructiveCapabilityPromise;
}

export async function destructiveActionsEnabled(): Promise<boolean> {
  return (await destructiveActionsAvailability()).state === 'enabled';
}

async function requireDestructiveActions(): Promise<void> {
  const availability = await destructiveActionsAvailability();
  if (availability.state === 'enabled') return;
  if (availability.state === 'disabled') throw new Error(availability.reason);
  throw new Error(`Destructive-action availability could not be verified. The action was not attempted. ${availability.error.message}`);
}

function withDestructiveActionGuard<T extends ResolvedLibraryDataSource>(source: T): T {
  const guardedAssets = new Proxy(source.assets, {
    get(target, property, receiver) {
      if (property !== 'trash') return Reflect.get(target, property, receiver);
      return async (...args: Parameters<typeof source.assets.trash>) => {
        await requireDestructiveActions();
        return source.assets.trash(...args);
      };
    },
  });

  const guardedDuplicates = new Proxy(source.duplicates, {
    get(target, property, receiver) {
      if (property !== 'executePlan') return Reflect.get(target, property, receiver);
      return async (...args: Parameters<typeof source.duplicates.executePlan>) => {
        const [plan] = args;
        if (Object.values(plan.resolution.decisions).includes('delete')) await requireDestructiveActions();
        return source.duplicates.executePlan(...args);
      };
    },
  });

  return {
    ...source,
    assets: guardedAssets,
    duplicates: guardedDuplicates,
  } as T;
}

// Single production composition point for the V2 UI. A V2 operation is live only when
// createApiLibraryDataSource explicitly implements it. Unsupported operations fail closed
// with V2NotImplementedError rather than falling back to demo data or an existing V1 API.
export const libraryData: LiveLibraryDataSource = withDestructiveActionGuard(
  createApiLibraryDataSource(),
);
