import { afterEach, describe, expect, it, vi } from 'vitest';

import { destructiveActionAvailability } from './capabilities';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('destructiveActionAvailability', () => {
  it('reports enabled when the server enables destructive actions', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ destructive_actions: true }), { status: 200, headers: { 'content-type': 'application/json' } })));
    await expect(destructiveActionAvailability()).resolves.toEqual({ state: 'enabled' });
  });

  it('reports disabled separately from transport failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ destructive_actions: false }), { status: 200, headers: { 'content-type': 'application/json' } })));
    await expect(destructiveActionAvailability()).resolves.toEqual({ state: 'disabled', reason: 'Destructive actions are disabled by server configuration.' });
  });

  it('reports unavailable when capability verification fails', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline'); }));
    const result = await destructiveActionAvailability();
    expect(result.state).toBe('unavailable');
    if (result.state === 'unavailable') expect(result.error.message).toContain('offline');
  });
});
