export type ViewerSelectionKey = Pick<KeyboardEvent, 'key' | 'defaultPrevented' | 'ctrlKey' | 'metaKey' | 'altKey'>;

export function isViewerSelectionShortcut(event: ViewerSelectionKey, interactiveTarget = false): boolean {
  return event.key === ' '
    && !event.defaultPrevented
    && !event.ctrlKey
    && !event.metaKey
    && !event.altKey
    && !interactiveTarget;
}
