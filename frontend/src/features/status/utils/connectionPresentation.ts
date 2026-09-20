import type { TaskConnectionState } from '../types/syncContracts';

export function connectionLabel(state: TaskConnectionState): string {
  switch (state) {
    case 'connected': return 'Live';
    case 'connecting': return 'Connecting';
    case 'reconnecting': return 'Reconnecting';
    default: return 'Disconnected';
  }
}

export function connectionTone(state: TaskConnectionState): 'ok' | 'warn' | 'default' {
  if (state === 'connected') return 'ok';
  if (state === 'disconnected') return 'warn';
  return 'default';
}
