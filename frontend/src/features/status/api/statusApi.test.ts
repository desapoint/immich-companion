import { describe, expect, it, vi } from 'vitest';

import { loadStatus, StatusApiError, type Fetcher } from './statusApi';

const payloads: Record<string, object> = {
  '/api/health': {
    status: 'ok',
    ready: true,
    environment: 'test',
    safe_mode: true,
    dependencies: {
      immich: { status: 'ok', configured: true, latency_ms: 2.5 },
      companion_database: { status: 'ok', configured: true, latency_ms: 1.2 },
    },
  },
  '/api/version': { name: 'immich-companion', version: 'test-version', environment: 'test' },
  '/api/capabilities': {
    destructive_actions: false,
    immich_api: true,
    companion_database: true,
    implemented: ['health'],
    planned: ['search'],
  },
};

describe('loadStatus', () => {
  it('loads all status contracts as one snapshot', async () => {
    const fetcher = vi.fn<Fetcher>(async (input) => {
      const path = String(input);
      return new Response(JSON.stringify(payloads[path]), {
        status: 200,
        headers: { 'content-type': 'application/json' },
      });
    });

    const snapshot = await loadStatus(fetcher);

    expect(fetcher).toHaveBeenCalledTimes(3);
    expect(snapshot.health.ready).toBe(true);
    expect(snapshot.version.version).toBe('test-version');
    expect(snapshot.capabilities.destructive_actions).toBe(false);
  });

  it('reports the failed endpoint and status without swallowing the error', async () => {
    const fetcher: Fetcher = async (input) => {
      const path = String(input);
      if (path === '/api/health') return new Response(null, { status: 503 });
      return new Response(JSON.stringify(payloads[path]), { status: 200 });
    };

    await expect(loadStatus(fetcher)).rejects.toEqual(
      new StatusApiError('/api/health', 503),
    );
  });
});
