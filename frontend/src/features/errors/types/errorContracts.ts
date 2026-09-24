export type TaskErrorOutcome = 'retrying' | 'failed';

export interface TaskErrorEvent {
  id: string;
  taskId: string;
  taskType: string;
  attempt: number;
  outcome: TaskErrorOutcome;
  errorType: string;
  message: string;
  retryable: boolean | null;
  willRetry: boolean;
  maxAttempts: number | null;
  occurredAt: string;
}
