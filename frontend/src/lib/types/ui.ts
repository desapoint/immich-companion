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
  | 'sync'
  | 'tag'
  | 'tag-add'
  | 'tag-remove'
  | 'trash'
  | 'unarchive'
  | 'unfavorite'
  | 'view'
  | 'keyboard'
  | 'more'
  | 'zoom-in'
  | 'zoom-out';

export interface ActionMenuItem {
  id: string;
  icon: IconName;
  label: string;
  disabled?: boolean;
  tone?: 'default' | 'destructive';
}
