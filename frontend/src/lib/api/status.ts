import { requestJson } from './http';
import { loadCapabilities } from './capabilities';
import type { HealthResponse, StatusSnapshot, VersionResponse } from '../types/status';

export async function loadStatus(signal?: AbortSignal): Promise<StatusSnapshot> {
  const [health, version, capabilities] = await Promise.all([
    requestJson<HealthResponse>('/api/health', { signal }),
    requestJson<VersionResponse>('/api/version', { signal }),
    loadCapabilities(signal),
  ]);

  return { health, version, capabilities };
}
