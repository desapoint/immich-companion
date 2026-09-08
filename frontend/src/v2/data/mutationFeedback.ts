import type { MutationResult } from './contracts';

export type OperationFeedback = {
  tone: 'pending' | 'ok' | 'warn' | 'bad';
  title: string;
  detail: string;
  failures: Array<{ id: string; reason: string }>;
};

export function errorMessage(error: unknown, fallback = 'The request could not be completed.'): string {
  if (error instanceof Error && error.message.trim()) return error.message;
  if (typeof error === 'string' && error.trim()) return error;
  return fallback;
}

export function pendingOperationFeedback(action: string, phase: 'applying' | 'refreshing'): OperationFeedback {
  return {
    tone: 'pending',
    title: phase === 'applying' ? `${action} in progress` : `${action} applied`,
    detail: phase === 'applying' ? 'Applying change…' : 'Refreshing latest asset state…',
    failures: [],
  };
}

export function mutationFeedback(action: string, result: MutationResult): OperationFeedback {
  const succeeded = result.affectedIds.length;
  const failed = result.failed.length;
  const total = succeeded + failed;

  if (failed === 0) {
    return {
      tone: 'ok',
      title: `${action} completed`,
      detail: `${succeeded.toLocaleString()} ${succeeded === 1 ? 'item' : 'items'} succeeded.`,
      failures: [],
    };
  }

  if (succeeded === 0) {
    return {
      tone: 'bad',
      title: `${action} failed`,
      detail: `${failed.toLocaleString()} ${failed === 1 ? 'item' : 'items'} failed.`,
      failures: result.failed,
    };
  }

  return {
    tone: 'warn',
    title: `${action} partially completed`,
    detail: `${succeeded.toLocaleString()} of ${total.toLocaleString()} succeeded · ${failed.toLocaleString()} failed.`,
    failures: result.failed,
  };
}
