import { describe, expect, it } from 'vitest';

import {
  ALL_RELATIONS_VALUE,
  relationDialogOptions,
  resolveRelationSelection,
  updateRelationSelection,
} from './relationAction';

const albums = [
  { value: 'album-1', label: 'Album one' },
  { value: 'album-2', label: 'Album two' },
];

describe('relation action selection', () => {
  it('adds an exclusive All choice to removal dialogs only', () => {
    expect(relationDialogOptions(albums, true, 'albums')[0]).toEqual({
      value: ALL_RELATIONS_VALUE,
      label: 'All albums',
    });
    expect(relationDialogOptions(albums, false, 'albums')).toEqual(albums);
    expect(updateRelationSelection([], ['album-1', ALL_RELATIONS_VALUE], true)).toEqual([
      ALL_RELATIONS_VALUE,
    ]);
    expect(updateRelationSelection(
      [ALL_RELATIONS_VALUE],
      [ALL_RELATIONS_VALUE, 'album-2'],
      true,
    )).toEqual(['album-2']);
  });

  it('expands All to every current relation ID before confirmation', () => {
    expect(resolveRelationSelection([ALL_RELATIONS_VALUE], albums)).toEqual([
      'album-1',
      'album-2',
    ]);
  });
});
