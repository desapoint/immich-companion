import type { AssetTaskStatus } from '../types/assets';

export function isTaskTerminal(status: AssetTaskStatus['status']): boolean {
  return status === 'completed' || status === 'failed' || status === 'cancelled';
}

/**
 * A task is still in flight when either its hydrated status is non-terminal or
 * its id remains persisted while status hydration/fallback polling catches up.
 */
export function isTaskTrackedInFlight(
  current: AssetTaskStatus | null,
  persistedTaskId: string | null,
): boolean {
  return persistedTaskId !== null || Boolean(current && !isTaskTerminal(current.status));
}

/**
 * Once a task reaches a terminal state, later non-terminal observations for
 * the same task are stale and must not regress UI state. Different task ids
 * are independent and may always replace one another.
 */
export function shouldApplyTaskStatus(
  current: AssetTaskStatus | null,
  next: AssetTaskStatus,
): boolean {
  if (!current || current.id !== next.id) return true;
  return !isTaskTerminal(current.status) || isTaskTerminal(next.status);
}
