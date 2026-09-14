import type { ManagedRelation } from '../types/relations';

export interface VisibleTagRow {
  item: ManagedRelation;
  depth: number;
  hasChildren: boolean;
}

/**
 * Flattens the currently loaded tag hierarchy. Branches are expanded by
 * default and the caller records only explicit collapses, so a collection
 * refresh cannot silently reopen something the user collapsed.
 */
export function flattenTagTree(
  nodes: ManagedRelation[],
  collapsed: Set<string>,
  forceExpanded = false,
): VisibleTagRow[] {
  const rows: VisibleTagRow[] = [];
  const visit = (node: ManagedRelation, depth: number) => {
    const children = node.children ?? [];
    rows.push({ item: node, depth, hasChildren: children.length > 0 });
    if ((forceExpanded || !collapsed.has(node.id)) && children.length) {
      for (const child of children) visit(child, depth + 1);
    }
  };
  for (const node of nodes) visit(node, 0);
  return rows;
}
