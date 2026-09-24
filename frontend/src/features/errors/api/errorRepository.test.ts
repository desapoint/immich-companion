import { afterEach, describe, expect, it, vi } from 'vitest';

import { clearTaskErrors, loadTaskErrors } from './errorRepository';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('Error Hub repository', () => {
  it('loads durable errors and maps backend field names', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify([{
      id: 'event-1',
      task_id: 'task-1',
      task_type: 'similarity_scan',
      attempt: 2,
      outcome: 'retrying',
      error_type: 'RetryableTaskError',
      message: 'Immich is temporarily unavailable.',
      retryable: true,
      will_retry: true,
      max_attempts: 5,
      occurred_at: '2026-09-24T10:00:00Z',
    }]), { headers: { 'content-type': 'application/json' } }));
    vi.stubGlobal('fetch', fetchMock);

    const errors = await loadTaskErrors(25);

    expect(fetchMock).toHaveBeenCalledWith('/api/errors?limit=25', expect.objectContaining({ headers: expect.any(Headers) }));
    expect(errors).toEqual([expect.objectContaining({
      taskId: 'task-1',
      taskType: 'similarity_scan',
      outcome: 'retrying',
      retryable: true,
      maxAttempts: 5,
    })]);
  });

  it('clears durable errors', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ cleared: 7 }), {
      headers: { 'content-type': 'application/json' },
    }));
    vi.stubGlobal('fetch', fetchMock);

    await expect(clearTaskErrors()).resolves.toBe(7);
    expect(fetchMock).toHaveBeenCalledWith('/api/errors', expect.objectContaining({
      method: 'DELETE',
      headers: expect.any(Headers),
    }));
  });
});
