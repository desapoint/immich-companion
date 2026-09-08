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
  it('separates apply and reconcile phases', async () => {
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
    expect(operation.phase).toBe('reconciling');
    releaseReconcile();
    await run;
    expect(operation.phase).toBe('idle');
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
});
