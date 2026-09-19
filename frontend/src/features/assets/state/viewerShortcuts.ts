import type { KeyboardShortcut } from '../../../lib/components/ui/KeyboardShortcuts.svelte';

export const assetViewerShortcuts: KeyboardShortcut[] = [
  { keys: 'Esc', description: 'Close viewer' },
  { keys: '←', description: 'Previous asset / stack member' },
  { keys: '→', description: 'Next asset / stack member' },
  { keys: 'Space', description: 'Toggle selection on shown asset' },
  { keys: 'F', description: 'Toggle favorite on shown asset' },
  { keys: 'A', description: 'Toggle archive on shown asset' },
  { keys: ['+', '='], description: 'Zoom in' },
  { keys: '−', description: 'Zoom out' },
  { keys: '0', description: 'Reset zoom / fit image' },
  { keys: '1', description: 'Actual pixel size (1:1)' },
];
