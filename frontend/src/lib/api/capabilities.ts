import { requestJson } from './http';
import type { CapabilitiesResponse } from '../types/status';

export type CapabilityAvailability =
  | { state: 'enabled' }
  | { state: 'disabled'; reason: string }
  | { state: 'unavailable'; error: Error };

export async function loadCapabilities(signal?: AbortSignal): Promise<CapabilitiesResponse> {
  return requestJson<CapabilitiesResponse>('/api/capabilities', { signal });
}

export async function destructiveActionAvailability(signal?: AbortSignal): Promise<CapabilityAvailability> {
  try {
    const capabilities = await loadCapabilities(signal);
    return capabilities.destructive_actions
      ? { state: 'enabled' }
      : { state: 'disabled', reason: 'Destructive actions are disabled by server configuration.' };
  } catch (error) {
    return {
      state: 'unavailable',
      error: error instanceof Error ? error : new Error('Capability availability could not be verified.'),
    };
  }
}
