import type { DuplicateDecision, DuplicateKeeperRule, DuplicateKeeperRuleField, DuplicateKeeperRuleOperator } from '../../../v2/data/contracts';

export type DuplicateAutomationConditionScope = 'group' | 'member' | 'any_member' | 'all_members' | 'no_members' | 'at_least_members';
export type DuplicateAutomationLogic = 'all' | 'any';
export type DuplicateAutomationTarget = 'matching_members' | 'remaining_members' | 'whole_group';
export type DuplicateAutomationAction = 'keep' | 'delete' | 'stack' | 'resolve_keeper' | 'leave_undecided' | 'manual_review';
export type DuplicateAutomationFlow = 'continue' | 'stop_affected' | 'stop_group';
export type DuplicateAutomationGroupField =
  | 'classification' | 'review_state' | 'member_count' | 'group_similarity' | 'discovery_source'
  | 'auto_ready' | 'selected' | 'eligible' | 'decision_count' | 'undecided_count';
export type DuplicateAutomationConditionField = DuplicateKeeperRuleField | DuplicateAutomationGroupField;

export type DuplicateAutomationUiCondition = {
  id: number;
  scope: DuplicateAutomationConditionScope;
  field: DuplicateAutomationConditionField;
  operator: DuplicateKeeperRuleOperator;
  value: string;
  count: number;
};
export type DuplicateAutomationUiRule = {
  id: number;
  logic: DuplicateAutomationLogic;
  conditions: DuplicateAutomationUiCondition[];
  target: DuplicateAutomationTarget;
  action: DuplicateAutomationAction;
  flow: DuplicateAutomationFlow;
};
export type DuplicateAutomationExistingDecision = {
  assetId: string;
  disposition: DuplicateDecision;
  source: 'manual' | 'automatic';
  status?: 'pending' | 'completed';
};
export type DuplicateAutomationDecision = Required<DuplicateAutomationExistingDecision>;
export type DuplicateAutomationEvaluation = {
  matched: boolean;
  touched: boolean;
  persistDraft: boolean;
  complete: boolean;
  partial: boolean;
  manualReview: boolean;
  ambiguous: boolean;
  preservedManual: boolean;
  matchedRuleCount: number;
  keepCount: number;
  deleteCount: number;
  stackCount: number;
  undecidedCount: number;
  metadataKeeperAssetId: string | null;
  decisions: DuplicateAutomationDecision[];
};
export type AutomationRuleValueKind = 'text' | 'number' | 'boolean';

export type AutomationGroupFieldDefinition = {
  value: DuplicateAutomationGroupField;
  label: string;
  kind: AutomationRuleValueKind;
};
