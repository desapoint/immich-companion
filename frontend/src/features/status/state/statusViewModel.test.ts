import { describe, expect, it } from 'vitest';

import {
  dependencyLabel,
  dependencyTone,
  formatLatency,
  healthLabel,
  healthTone,
  humanizeIdentifier,
} from './statusViewModel';
import type { HealthResponse } from '../types/status';

const health: HealthResponse = {
  status: 'ok',
  ready: true,
  environment: 'test',
  safe_mode: true,
  dependencies: { immich: { status: 'ok', configured: true, latency_ms: 4.25 } },
};

describe('status view model', () => {
  it('maps healthy and degraded states to text as well as color tones', () => {
    expect(healthLabel(health)).toBe('Operational');
    expect(healthTone(health)).toBe('positive');
    expect(healthLabel({ ...health, ready: false, status: 'degraded' })).toBe('Needs attention');
    expect(healthTone({ ...health, ready: false, status: 'degraded' })).toBe('warning');
  });

  it('distinguishes unavailable and unconfigured dependencies', () => {
    expect(dependencyLabel({ status: 'not_configured', configured: false })).toBe('Not configured');
    expect(dependencyTone({ status: 'not_configured', configured: false })).toBe('warning');
    expect(dependencyLabel({ status: 'error', configured: true })).toBe('Connection error');
    expect(dependencyTone({ status: 'error', configured: true })).toBe('negative');
  });

  it('formats machine identifiers and latency for display', () => {
    expect(humanizeIdentifier('visual_similarity')).toBe('Visual Similarity');
    expect(formatLatency(4.25)).toBe('4.3 ms');
    expect(formatLatency(undefined)).toBe('Not reported');
  });
});
