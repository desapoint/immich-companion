import { describe, expect, it } from 'vitest';

import { ApiError } from '../../shared/api/http';
import { isAssetSelectionUnavailableError, isTaskUnavailableError } from './assetApi';

describe('asset API errors', () => {
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

  it('only retires tracked tasks for a definitive not-found response', () => {
    expect(isTaskUnavailableError(
      new ApiError('The task was not found.', 404, 'The task was not found.'),
    )).toBe(true);
    expect(isTaskUnavailableError(
      new ApiError('The companion database is not configured.', 503),
    )).toBe(false);
    expect(isTaskUnavailableError(new Error('network failed'))).toBe(false);
  });
});
