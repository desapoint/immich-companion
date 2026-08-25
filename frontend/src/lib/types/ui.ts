export type StatusTone = 'positive' | 'warning' | 'negative' | 'neutral';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export type IconName =
  | 'album'
  | 'album-add'
  | 'album-remove'
  | 'actual-size'
  | 'archive'
  | 'check'
  | 'clear-selection'
  | 'close'
  | 'external'
  | 'favorite'
  | 'fit'
  | 'info'
  | 'immich'
  | 'invert-selection'
  | 'restore'
  | 'reset-zoom'
  | 'select'
  | 'select-all'
  | 'select-page'
  | 'stack'
  | 'tag'
  | 'tag-add'
  | 'tag-remove'
  | 'trash'
  | 'unarchive'
  | 'unfavorite'
  | 'view'
  | 'keyboard'
  | 'zoom-in'
  | 'zoom-out';
