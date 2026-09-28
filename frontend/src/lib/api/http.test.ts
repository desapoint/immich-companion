import { afterEach, describe, expect, it, vi } from 'vitest';

import { requestJson } from './http';

afterEach(() => vi.unstubAllGlobals());

describe('HTTP validation errors', () => {
  it('includes the invalid settings field from FastAPI responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: [{ loc: ['body', 'full_batch_size'], msg: 'Input should be less than or equal to 1000' }],
    }), { status: 422, headers: { 'content-type': 'application/json' } })));

    await expect(requestJson('/api/settings/sync/runtime')).rejects.toThrow(
      'full_batch_size: Input should be less than or equal to 1000',
    );
  });
});
