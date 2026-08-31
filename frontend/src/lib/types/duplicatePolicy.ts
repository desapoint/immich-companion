export type DuplicateKeeperPolicy = 'most_recent' | 'prefer_upload' | 'prefer_external' | 'first';
export type ExactFilePolicyAction = 'resolve' | 'keep_all' | 'stack_all' | 'review';

export interface DuplicatePolicy {
  automatic_handling_enabled: boolean;
  preselect_safe_groups: boolean;
  exact_file_action: ExactFilePolicyAction;
  keeper_policy: DuplicateKeeperPolicy;
  analyze_automatically: boolean;
  verify_upload_streams: boolean;
  external_library_ids: string[];
}

export interface ImmichLibraryOption {
  id: string;
  name: string;
  type: string | null;
  assetCount: number | null;
}
