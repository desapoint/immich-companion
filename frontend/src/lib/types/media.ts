export type MediaPreviewSource = 'stack' | 'similar';
export type MediaPreviewActivation = 'click' | 'hover' | 'press';

export interface MediaPreviewItem {
  id: string;
  label: string;
  thumbnailUrl: string;
  meta?: string | null;
  isPrimary?: boolean;
}
