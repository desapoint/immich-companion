import type { TaskConnectionState } from '../types/syncContracts';

export function connectionLabel(state: TaskConnectionState): string {
  switch (state) {
    case 'connected': return 'Live updates';
    case 'connecting': return 'Connecting live updates';
    case 'reconnecting': return 'Reconnecting live updates';
    default: return 'Live updates unavailable';
  }
}

export function connectionTone(state: TaskConnectionState): 'ok' | 'warn' | 'default' {
  if (state === 'connected') return 'ok';
  if (state === 'disconnected') return 'warn';
  return 'default';
}
