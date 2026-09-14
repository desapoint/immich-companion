import { describe, expect, it } from 'vitest';

import { ApiError } from '../../shared/api/http';
import { isAssetSelectionUnavailableError } from './assetApi';

describe('asset selection API errors', () => {
  it('recognizes expired and missing server selections', () => {
    expect(isAssetSelectionUnavailableError(
      new ApiError('Selection set has expired', 413, 'Selection set has expired'),
    )).toBe(true);
    expect(isAssetSelectionUnavailableError(
      new ApiError(
        'Selection set was not found or has expired',
        413,
        'Selection set was not found or has expired',
      ),
    )).toBe(true);
  });

  it('does not classify revision conflicts or unrelated failures as expiry', () => {
    expect(isAssetSelectionUnavailableError(
      new ApiError(
        'Selection set changed; reload its membership',
        413,
        'Selection set changed; reload its membership',
      ),
    )).toBe(false);
    expect(isAssetSelectionUnavailableError(new Error('network failed'))).toBe(false);
  });
});
