import type { ManagedRelation } from '../types/relations';

export interface VisibleTagRow {
  item: ManagedRelation;
  depth: number;
  hasChildren: boolean;
}

export function branchParentIds(nodes: ManagedRelation[]): string[] {
  const ids: string[] = [];
  for (const node of nodes) {
    if (node.children?.length) ids.push(node.id, ...branchParentIds(node.children));
  }
  return ids;
}

export function flattenTagTree(
  nodes: ManagedRelation[],
  expanded: Set<string>,
  forceExpanded = false,
): VisibleTagRow[] {
  const rows: VisibleTagRow[] = [];
  const visit = (node: ManagedRelation, depth: number) => {
    const children = node.children ?? [];
    rows.push({ item: node, depth, hasChildren: children.length > 0 });
    if ((forceExpanded || expanded.has(node.id)) && children.length) {
      for (const child of children) visit(child, depth + 1);
    }
  };
  for (const node of nodes) visit(node, 0);
  return rows;
}
