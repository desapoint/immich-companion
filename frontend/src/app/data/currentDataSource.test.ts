import { beforeEach, describe, expect, it, vi } from 'vitest';

const availability = vi.hoisted(() => vi.fn());

vi.mock('../../lib/api/capabilities', () => ({
  destructiveActionAvailability: availability,
}));
vi.mock('./apiLibraryDataSource.svelte', () => ({
  createApiLibraryDataSource: () => ({ assets: {}, duplicates: {} }),
}));
vi.mock('../../features/duplicates/state/duplicateWorkspaceWriteBarrier', () => ({
  withDuplicateWorkspaceWriteBarrier: (source: unknown) => source,
}));

let loadAvailability: () => Promise<import('../../lib/api/capabilities').CapabilityAvailability>;

describe('destructive action availability caching', () => {
  beforeEach(async () => {
    vi.resetModules();
    availability.mockReset();
    const module = await import('./currentDataSource.svelte');
    loadAvailability = module.destructiveActionsAvailability;
  });

  it('shares a concurrent request but retries after an unavailable result', async () => {
    let resolveFirst: ((value: { state: 'unavailable'; error: Error }) => void) | undefined;
    availability
      .mockImplementationOnce(() => new Promise((resolve) => { resolveFirst = resolve; }))
      .mockResolvedValueOnce({ state: 'enabled' });

    const first = loadAvailability();
    const concurrent = loadAvailability();
    expect(first).toBe(concurrent);
    expect(availability).toHaveBeenCalledTimes(1);

    resolveFirst?.({ state: 'unavailable', error: new Error('offline') });
    await expect(first).resolves.toMatchObject({ state: 'unavailable' });
    await expect(loadAvailability()).resolves.toEqual({ state: 'enabled' });
    expect(availability).toHaveBeenCalledTimes(2);
  });

  it('retains a stable server decision after the request completes', async () => {
    availability.mockResolvedValue({ state: 'disabled', reason: 'disabled by policy' });

    await expect(loadAvailability()).resolves.toEqual({ state: 'disabled', reason: 'disabled by policy' });
    await expect(loadAvailability()).resolves.toEqual({ state: 'disabled', reason: 'disabled by policy' });
    expect(availability).toHaveBeenCalledTimes(1);
  });
});
