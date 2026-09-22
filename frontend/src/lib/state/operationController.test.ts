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
  it('keeps the operation locked while a refresh runs in the background', async () => {
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
    expect(operation.busy).toBe(true);
    expect(operation.reconciling).toBe(true);
    expect(operation.phase).toBe('reconciling');
    expect(operation.feedback?.tone).toBe('pending');
    releaseReconcile();
    await operation.waitForReconciliation();
    expect(operation.busy).toBe(false);
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

  it('rejects another action while refresh is still running', async () => {
    const operation = new OperationController();
    let release!: () => void;
    const firstRefresh = new Promise<void>((resolve) => release = resolve);
    const refreshes: string[] = [];
    await operation.run('First', async () => 1, { pending, outcome, reconcile: async () => { refreshes.push('first'); await firstRefresh; } });
    await Promise.resolve();
    expect(operation.reconciling).toBe(true);
    expect(await operation.run('Second', async () => 2, { pending, outcome, reconcile: async () => { refreshes.push('second'); } })).toBeNull();
    expect(await operation.run('Third', async () => 3, { pending, outcome, reconcile: async () => { refreshes.push('third'); } })).toBeNull();
    release();
    await operation.waitForReconciliation();
    expect(refreshes).toEqual(['first']);
    expect(operation.feedback?.title).toBe('done');
  });

  it('reports a refresh failure after the operation remains locked', async () => {
    const operation = new OperationController();
    let fail!: (error: Error) => void;
    const firstRefresh = new Promise<void>((_resolve, reject) => fail = reject);
    await operation.run('First', async () => 1, { pending, outcome, reconcile: () => firstRefresh });
    await Promise.resolve();
    expect(await operation.run('Second', async () => 2, { pending, outcome, reconcile: async () => {} })).toBeNull();
    fail(new Error('old failure'));
    await operation.waitForReconciliation();
    expect(operation.error).toContain('old failure');
    expect(operation.busy).toBe(false);
  });

  it('notifies an error handler when the operation fails before reconciliation', async () => {
    const onError = vi.fn();
    const operation = new OperationController(onError);

    expect(await operation.run('Save', async () => {
      throw new Error('A stack needs at least two surviving members');
    }, { pending, outcome })).toBeNull();

    expect(operation.error).toBe('A stack needs at least two surviving members');
    expect(onError).toHaveBeenCalledWith('A stack needs at least two surviving members');
  });

  it('notifies an error handler when reconciliation fails', async () => {
    const onError = vi.fn();
    const operation = new OperationController(onError);
    await operation.run('Save', async () => ({ id: 'x' }), {
      pending,
      outcome,
      reconcile: async () => { throw new Error('refresh failed'); },
      reconcileError: 'Save was applied, but latest state could not be loaded.',
    });
    await operation.waitForReconciliation();

    expect(onError).toHaveBeenCalledWith(
      'Save was applied, but latest state could not be loaded. refresh failed',
    );
  });
});
