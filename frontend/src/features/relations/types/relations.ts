export type RelationKind = 'albums' | 'tags';

export interface ManagedRelation {
  id: string;
  name: string;
  description?: string;
  color?: string | null;
  parent_id?: string | null;
  parent_path?: string[];
  asset_count: number;
  children?: ManagedRelation[];
}

export interface RelationPage {
  items: ManagedRelation[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
