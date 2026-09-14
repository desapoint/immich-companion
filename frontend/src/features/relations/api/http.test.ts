import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, requestJson, requestVoid } from './http';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('shared HTTP client', () => {
  it('adds JSON headers and serializes json bodies', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: '1' }), {
      status: 200,
      headers: { 'content-type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(requestJson<{ id: string }>('/api/example', {
      method: 'POST',
      json: { name: 'Example' },
    })).resolves.toEqual({ id: '1' });

    expect(fetchMock).toHaveBeenCalledOnce();
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.get('accept')).toBe('application/json');
    expect(headers.get('content-type')).toBe('application/json');
    expect(init.body).toBe(JSON.stringify({ name: 'Example' }));
  });

  it('surfaces API detail and status through ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: 'Relation name already exists.',
    }), {
      status: 409,
      headers: { 'content-type': 'application/json' },
    })));

    const error = await requestJson('/api/example').catch((reason) => reason);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      message: 'Relation name already exists.',
      status: 409,
      detail: 'Relation name already exists.',
    });
  });

  it('supports empty successful responses and preserves abort signals', async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetchMock);
    const controller = new AbortController();

    await expect(requestVoid('/api/example', {
      method: 'DELETE',
      signal: controller.signal,
    })).resolves.toBeUndefined();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.signal).toBe(controller.signal);
  });
});
