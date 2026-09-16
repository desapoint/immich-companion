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
    companion_database: DependencyStatus;
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
  companion_database: boolean;
  immich_server?: ImmichCompatibilityResponse;
  implemented: string[];
  planned: string[];
}

export interface ImmichCompatibilityResponse {
  status: 'compatible' | 'incompatible' | 'unknown';
  server_version: {
    major: number;
    minor: number;
    patch: number;
    prerelease: number | null;
  } | null;
  supported_api_version: string;
  detail: string;
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
