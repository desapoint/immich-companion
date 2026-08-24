export interface DependencyStatus {
  status: string;
  configured: boolean;
  detail?: string;
  latency_ms?: number;
}

export interface HealthResponse {
  status: 'ok' | 'degraded';
  ready: boolean;
  environment: string;
  safe_mode: boolean;
  dependencies: {
    immich: DependencyStatus;
  };
}

export interface VersionResponse {
  name: string;
  version: string;
  environment: string;
}

export interface CapabilitiesResponse {
  destructive_actions: boolean;
  immich_api: boolean;
  implemented: string[];
  planned: string[];
}

export interface StatusSnapshot {
  health: HealthResponse;
  version: VersionResponse;
  capabilities: CapabilitiesResponse;
}

export type StatusLoadState =
  | { kind: 'loading' }
  | { kind: 'loaded'; snapshot: StatusSnapshot }
  | { kind: 'error'; message: string };
