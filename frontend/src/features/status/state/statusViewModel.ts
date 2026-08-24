import type { DependencyStatus, HealthResponse } from '../types/status';
import type { StatusTone } from '../../../lib/types/ui';

export function healthLabel(health: HealthResponse): string {
  return health.ready ? 'Operational' : 'Needs attention';
}

export function healthTone(health: HealthResponse): StatusTone {
  return health.ready ? 'positive' : 'warning';
}

export function dependencyLabel(dependency: DependencyStatus): string {
  if (dependency.status === 'ok') return 'Connected';
  if (dependency.status === 'not_configured') return 'Not configured';
  return 'Connection error';
}

export function dependencyTone(dependency: DependencyStatus): StatusTone {
  if (dependency.status === 'ok') return 'positive';
  if (dependency.status === 'not_configured') return 'warning';
  return 'negative';
}

export function formatLatency(latency: number | undefined): string {
  return latency === undefined ? 'Not reported' : `${latency.toFixed(1)} ms`;
}

export function humanizeIdentifier(value: string): string {
  return value
    .split('_')
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}
