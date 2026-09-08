import { requestJson } from './http';
import type { CapabilitiesResponse, HealthResponse, StatusSnapshot, VersionResponse } from '../types/status';

export async function loadStatus(signal?: AbortSignal): Promise<StatusSnapshot> {
  const [health, version, capabilities] = await Promise.all([
    requestJson<HealthResponse>('/api/health', { signal }),
    requestJson<VersionResponse>('/api/version', { signal }),
    requestJson<CapabilitiesResponse>('/api/capabilities', { signal }),
  ]);

  return { health, version, capabilities };
}
