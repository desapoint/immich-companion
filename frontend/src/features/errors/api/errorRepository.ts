import { requestJson } from '../../../lib/api/http';
import type { TaskErrorEvent, TaskErrorOutcome } from '../types/errorContracts';

type ApiTaskErrorEvent = {
  id: string;
  task_id: string;
  task_type: string;
  attempt: number;
  outcome: TaskErrorOutcome;
  error_type: string;
  message: string;
  retryable: boolean | null;
  will_retry: boolean;
  max_attempts: number | null;
  occurred_at: string;
};

function normalizeError(error: ApiTaskErrorEvent): TaskErrorEvent {
  return {
    id: error.id,
    taskId: error.task_id,
    taskType: error.task_type,
    attempt: error.attempt,
    outcome: error.outcome,
    errorType: error.error_type,
    message: error.message,
    retryable: error.retryable,
    willRetry: error.will_retry,
    maxAttempts: error.max_attempts,
    occurredAt: error.occurred_at,
  };
}

export async function loadTaskErrors(limit = 200, signal?: AbortSignal): Promise<TaskErrorEvent[]> {
  const errors = await requestJson<ApiTaskErrorEvent[]>(`/api/errors?limit=${limit}`, { signal });
  return errors.map(normalizeError);
}

export async function clearTaskErrors(): Promise<number> {
  const result = await requestJson<{ cleared: number }>('/api/errors', { method: 'DELETE' });
  return result.cleared;
}
