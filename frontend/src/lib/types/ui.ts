export type StatusTone = 'positive' | 'warning' | 'negative' | 'neutral';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}
