import { describe, expect, it } from 'vitest';

import type { AssetTaskStatus } from '../types/assets';
import { isTaskTerminal, shouldApplyTaskStatus } from './taskStatus';

function task(id: string, status: AssetTaskStatus['status']): AssetTaskStatus {
  return {
    id,
    task_type: 'asset_action',
    status,
    payload: {},
    checkpoint: {},
    counters: {},
    progress: {},
    result: null,
    error: null,
    attempt: 1,
    next_attempt_at: null,
    created_at: '2026-09-14T00:00:00Z',
    started_at: null,
    completed_at: null,
  };
}

describe('task status ordering', () => {
  it('treats only final task states as terminal', () => {
    expect(isTaskTerminal('completed')).toBe(true);
    expect(isTaskTerminal('failed')).toBe(true);
    expect(isTaskTerminal('cancelled')).toBe(true);
    expect(isTaskTerminal('cancel_requested')).toBe(false);
    expect(isTaskTerminal('retrying')).toBe(false);
  });

  it('rejects a stale non-terminal observation after the same task completed', () => {
    expect(shouldApplyTaskStatus(task('task-1', 'completed'), task('task-1', 'running'))).toBe(false);
    expect(shouldApplyTaskStatus(task('task-1', 'failed'), task('task-1', 'retrying'))).toBe(false);
  });

  it('still accepts duplicate terminal observations and a different task id', () => {
    expect(shouldApplyTaskStatus(task('task-1', 'completed'), task('task-1', 'completed'))).toBe(true);
    expect(shouldApplyTaskStatus(task('task-1', 'completed'), task('task-2', 'queued'))).toBe(true);
  });
});
