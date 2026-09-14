import { describe, expect, it } from 'vitest';

import { LatestRequest, requestErrorMessage } from './latestRequest';

describe('LatestRequest', () => {
  it('aborts superseded work and only accepts the latest completion', async () => {
    const lifecycle = new LatestRequest();
    let resolveFirst!: (value: string) => void;
    let firstSignal!: AbortSignal;
    const first = lifecycle.run((signal) => {
      firstSignal = signal;
      return new Promise<string>((resolve) => { resolveFirst = resolve; });
    });

    const second = lifecycle.run(async () => 'new');
    expect(firstSignal.aborted).toBe(true);

    resolveFirst('old');
    const [oldResult, newResult] = await Promise.all([first, second]);
    expect(oldResult.status).toBe('aborted');
    expect(newResult).toMatchObject({ status: 'success', value: 'new' });
  });

  it('reports real failures without throwing them through request owners', async () => {
    const lifecycle = new LatestRequest();
    const result = await lifecycle.run(async () => {
      throw new Error('Nope');
    });

    expect(result.status).toBe('error');
    if (result.status === 'error') expect(result.error).toEqual(new Error('Nope'));
    expect(lifecycle.active).toBe(false);
  });

  it('invalidates a completed result when newer work starts before it is applied', async () => {
    const lifecycle = new LatestRequest();
    const completed = await lifecycle.run(async () => 'first');
    expect(completed.status).toBe('success');
    expect(lifecycle.isCurrent(completed.version)).toBe(true);

    void lifecycle.run(async () => 'second');
    expect(lifecycle.isCurrent(completed.version)).toBe(false);
  });

  it('treats explicit aborts as stale and releases the controller', async () => {
    const lifecycle = new LatestRequest();
    let resolve!: () => void;
    const pending = lifecycle.run(() => new Promise<void>((done) => { resolve = done; }));

    lifecycle.abort();
    resolve();
    expect((await pending).status).toBe('aborted');
    expect(lifecycle.active).toBe(false);
  });
});

describe('requestErrorMessage', () => {
  it('uses a meaningful Error message and otherwise falls back', () => {
    expect(requestErrorMessage(new Error('Useful'), 'Fallback')).toBe('Useful');
    expect(requestErrorMessage(new Error('   '), 'Fallback')).toBe('Fallback');
    expect(requestErrorMessage('bad', 'Fallback')).toBe('Fallback');
  });
});
