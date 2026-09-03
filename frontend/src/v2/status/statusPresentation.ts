import type { DependencyStatus, StatusSnapshot } from '../../features/status/types/status';

export type V2Tone = 'default' | 'ok' | 'warn' | 'bad';

export interface DisplayState {
  label: string;
  tone: V2Tone;
}

export function companionState(snapshot: StatusSnapshot): DisplayState {
  return snapshot.health.ready
    ? { label: 'Healthy', tone: 'ok' }
    : { label: 'Degraded', tone: 'warn' };
}

export function dependencyState(dependency: DependencyStatus, okLabel = 'Connected'): DisplayState {
  if (!dependency.configured) return { label: 'Not configured', tone: 'warn' };
  if (dependency.status === 'ok') return { label: okLabel, tone: 'ok' };
  return { label: 'Unavailable', tone: 'bad' };
}

export function immichVersion(snapshot: StatusSnapshot): string {
  const version = snapshot.capabilities.immich_server?.server_version;
  if (!version) return 'Unknown';
  return `${version.major}.${version.minor}.${version.patch}${version.prerelease == null ? '' : `-${version.prerelease}`}`;
}

export function capabilityLabel(capability: string): string {
  return capability.replaceAll('_', ' ');
}
