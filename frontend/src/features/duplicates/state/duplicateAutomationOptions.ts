import type { DuplicateKeeperRuleField, DuplicateKeeperRuleOperator } from '../types/contracts';
import { keeperOperatorOptions, keeperRuleFieldOptions } from './duplicateKeeperRules';
import type {
  AutomationGroupFieldDefinition,
  DuplicateAutomationConditionField,
  DuplicateAutomationConditionScope,
  DuplicateAutomationFlow,
  DuplicateAutomationTarget,
  DuplicateAutomationAction,
  DuplicateAutomationUiCondition,
  DuplicateAutomationUiRule,
} from './duplicateAutomationTypes';

export const automationGroupFields: AutomationGroupFieldDefinition[] = [
  { value: 'classification', label: 'Classification', kind: 'text' },
  { value: 'review_state', label: 'Review state', kind: 'text' },
  { value: 'member_count', label: 'Member count', kind: 'number' },
  { value: 'group_similarity', label: 'Group minimum similarity', kind: 'number' },
  { value: 'discovery_source', label: 'Discovery source', kind: 'text' },
  { value: 'auto_ready', label: 'Auto-ready', kind: 'boolean' },
  { value: 'selected', label: 'Selected', kind: 'boolean' },
  { value: 'eligible', label: 'Eligible', kind: 'boolean' },
  { value: 'decision_count', label: 'Saved decision count', kind: 'number' },
  { value: 'undecided_count', label: 'Undecided member count', kind: 'number' },
];
export const automationConditionScopeOptions = [
  { value: 'group', label: 'Group', subtitle: 'Match a property of the whole duplicate group' },
  { value: 'member', label: 'Member', subtitle: 'Match individual members and expose them as targets' },
  { value: 'any_member', label: 'Any member', subtitle: 'Group matches when at least one member matches' },
  { value: 'all_members', label: 'All members', subtitle: 'Group matches only when every member matches' },
  { value: 'no_members', label: 'No members', subtitle: 'Group matches only when no member matches' },
  { value: 'at_least_members', label: 'At least N members', subtitle: 'Group matches when enough members match' },
] as const;
export const automationTargetOptions = [
  { value: 'matching_members', label: 'Matching members', subtitle: 'Only members matched by Member conditions' },
  { value: 'remaining_members', label: 'Remaining undecided members', subtitle: 'Only members not already decided by an earlier rule or manual choice' },
  { value: 'whole_group', label: 'Whole group', subtitle: 'Apply across the group while preserving protected manual choices' },
] as const;
export const automationActionOptions = [
  { value: 'keep', label: 'Keep', subtitle: 'Write Keep only for the targeted members' },
  { value: 'delete', label: 'Delete', subtitle: 'Write Delete only for the targeted members; never auto-delete every member' },
  { value: 'stack', label: 'Stack', subtitle: 'Write Stack for the targeted members; primary can be reviewed later' },
  { value: 'resolve_keeper', label: 'Resolve using keeper priority', subtitle: 'Pick one keeper from the targeted undecided members and mark the rest Delete' },
  { value: 'leave_undecided', label: 'Leave undecided', subtitle: 'Intentionally make no decision for the targeted members' },
  { value: 'manual_review', label: 'Require manual review', subtitle: 'Select the group for review without assigning member decisions' },
] as const;
export const automationFlowOptions = [
  { value: 'continue', label: 'Continue', subtitle: 'Allow later rules to handle remaining undecided members' },
  { value: 'stop_affected', label: 'Stop for affected members', subtitle: 'Later rules cannot touch the targeted members' },
  { value: 'stop_group', label: 'Stop this group', subtitle: 'Do not evaluate any later rules for this group' },
] as const;

const textOperators: Array<{ value: DuplicateKeeperRuleOperator; label: string }> = [
  { value: 'is', label: 'is' }, { value: 'is_not', label: 'is not' }, { value: 'contains', label: 'contains' },
  { value: 'not_contains', label: 'does not contain' }, { value: 'starts_with', label: 'starts with' }, { value: 'ends_with', label: 'ends with' },
];
const numericOperators: Array<{ value: DuplicateKeeperRuleOperator; label: string }> = [
  { value: 'is', label: 'is equal to' }, { value: 'gte', label: 'is at least' }, { value: 'lte', label: 'is at most' },
  { value: 'gt', label: 'is greater than' }, { value: 'lt', label: 'is less than' },
];
const booleanOperators: Array<{ value: DuplicateKeeperRuleOperator; label: string }> = [
  { value: 'is_true', label: 'is true' }, { value: 'is_false', label: 'is false' },
];
function groupFieldDefinition(field: DuplicateAutomationConditionField) {
  return automationGroupFields.find((item) => item.value === field) ?? automationGroupFields[0];
}
export function automationConditionFieldOptions(scope: DuplicateAutomationConditionScope) {
  return scope === 'group' ? automationGroupFields.map(({ value, label }) => ({ value, label })) : keeperRuleFieldOptions;
}
export function automationOperatorOptions(condition: Pick<DuplicateAutomationUiCondition, 'scope' | 'field'>) {
  if (condition.scope !== 'group') return keeperOperatorOptions(condition.field as DuplicateKeeperRuleField, 'require');
  const definition = groupFieldDefinition(condition.field);
  if (definition.kind === 'boolean') return booleanOperators;
  return definition.kind === 'number' ? numericOperators : textOperators;
}
export function automationConditionNeedsValue(condition: Pick<DuplicateAutomationUiCondition, 'operator'>) {
  return !['highest', 'lowest', 'is_true', 'is_false'].includes(condition.operator);
}
export function newAutomationCondition(id: number, scope: DuplicateAutomationConditionScope = 'member', field: DuplicateAutomationConditionField = 'library', operator: DuplicateKeeperRuleOperator = 'is', value = 'upload'): DuplicateAutomationUiCondition {
  return { id, scope, field, operator, value, count: 1 };
}
export function newAutomationRule(id: number, conditionId: number): DuplicateAutomationUiRule {
  return { id, logic: 'all', conditions: [newAutomationCondition(conditionId)], target: 'matching_members', action: 'keep', nonMatchAction: 'none', flow: 'stop_group' };
}
export const automationPresetNames = ['Protect uploads for review', 'Resolve exact copies', 'Keep groups below 98%', 'Protect favorites for review'] as const;
export type AutomationPresetName = typeof automationPresetNames[number];
export function automationPreset(name: AutomationPresetName, nextRuleId: () => number, nextConditionId: () => number): DuplicateAutomationUiRule[] {
  const condition = (scope: DuplicateAutomationConditionScope, field: DuplicateAutomationConditionField, operator: DuplicateKeeperRuleOperator, value = '') => newAutomationCondition(nextConditionId(), scope, field, operator, value);
  const rule = (conditions: DuplicateAutomationUiCondition[], target: DuplicateAutomationTarget, action: DuplicateAutomationAction, flow: DuplicateAutomationFlow = 'stop_group'): DuplicateAutomationUiRule => ({ id: nextRuleId(), logic: 'all', conditions, target, action, nonMatchAction: 'none', flow });
  if (name === 'Resolve exact copies') return [rule([condition('group', 'classification', 'is', 'exact file, exact pixels')], 'whole_group', 'resolve_keeper')];
  if (name === 'Keep groups below 98%') return [rule([condition('group', 'group_similarity', 'lt', '98')], 'whole_group', 'keep')];
  if (name === 'Protect favorites for review') return [rule([condition('member', 'favorite', 'is_true')], 'matching_members', 'keep')];
  return [rule([condition('member', 'library', 'is', 'upload')], 'matching_members', 'keep')];
}
export function automationRuleValid(rule: DuplicateAutomationUiRule): boolean {
  if (!rule.conditions.length) return false;
  if (rule.target === 'matching_members' && !rule.conditions.some((condition) => condition.scope === 'member')) return false;
  return rule.conditions.every((condition) => {
    if (condition.scope === 'at_least_members' && (!Number.isFinite(condition.count) || condition.count < 1)) return false;
    return !automationConditionNeedsValue(condition) || condition.value.trim().length > 0;
  });
}
