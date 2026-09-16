import { describe, expect, it, vi } from 'vitest';

import { OperationController } from './operationController.svelte';

const pending = (phase: 'applying' | 'reconciling') => ({
  tone: 'pending' as const,
  title: phase,
  detail: phase,
  failures: [],
});

const outcome = () => ({ tone: 'ok' as const, title: 'done', detail: 'done', failures: [] });

describe('OperationController', () => {
  it('returns after apply while a refresh runs in the background', async () => {
    const operation = new OperationController();
    let releaseApply!: () => void;
    let releaseReconcile!: () => void;
    const applying = new Promise<void>((resolve) => releaseApply = resolve);
    const reconciling = new Promise<void>((resolve) => releaseReconcile = resolve);
    const run = operation.run('Save', async () => {
      await applying;
      return { id: 'x' };
    }, {
      pending,
      outcome,
      reconcile: async () => { await reconciling; },
    });

    expect(operation.phase).toBe('applying');
    releaseApply();
    await Promise.resolve();
    await Promise.resolve();
    expect(await run).toEqual({ id: 'x' });
    expect(operation.busy).toBe(false);
    expect(operation.reconciling).toBe(true);
    expect(operation.phase).toBe('idle');
    expect(operation.feedback?.tone).toBe('ok');
    releaseReconcile();
    await operation.waitForReconciliation();
    expect(operation.phase).toBe('idle');
    expect(operation.reconciling).toBe(false);
    expect(operation.feedback?.tone).toBe('ok');
  });

  it('keeps the successful outcome when reconciliation fails', async () => {
    const operation = new OperationController();
    await operation.run('Save', async () => ({ id: 'x' }), {
      pending,
      outcome,
      reconcile: async () => { throw new Error('refresh failed'); },
      reconcileError: 'Save was applied, but latest state could not be loaded.',
    });
    await operation.waitForReconciliation();

    expect(operation.feedback?.tone).toBe('ok');
    expect(operation.error).toContain('Save was applied');
    expect(operation.error).toContain('refresh failed');
  });

  it('publishes a retry prepared from the result', async () => {
    const operation = new OperationController();
    const retry = vi.fn(async () => {});
    await operation.run('Save', async () => ({ failed: true }), {
      pending,
      outcome,
      retry: () => retry,
    });

    expect(operation.retry).toBe(retry);
  });

  it('allows another action during refresh and coalesces queued refreshes', async () => {
    const operation = new OperationController();
    let release!: () => void;
    const firstRefresh = new Promise<void>((resolve) => release = resolve);
    const refreshes: string[] = [];
    await operation.run('First', async () => 1, { pending, outcome, reconcile: async () => { refreshes.push('first'); await firstRefresh; } });
    await Promise.resolve();
    expect(operation.reconciling).toBe(true);
    await operation.run('Second', async () => 2, { pending, outcome, reconcile: async () => { refreshes.push('second'); } });
    await operation.run('Third', async () => 3, { pending, outcome, reconcile: async () => { refreshes.push('third'); } });
    release();
    await operation.waitForReconciliation();
    expect(refreshes).toEqual(['first', 'third']);
    expect(operation.feedback?.title).toBe('done');
  });

  it('does not let an older refresh failure overwrite a newer action', async () => {
    const operation = new OperationController();
    let fail!: (error: Error) => void;
    const firstRefresh = new Promise<void>((_resolve, reject) => fail = reject);
    await operation.run('First', async () => 1, { pending, outcome, reconcile: () => firstRefresh });
    await Promise.resolve();
    await operation.run('Second', async () => 2, { pending, outcome, reconcile: async () => {} });
    fail(new Error('old failure'));
    await operation.waitForReconciliation();
    expect(operation.error).toBe('');
  });
});
