import { describe, expect, it } from 'vitest';

import { BoundedCache } from './boundedCache';

describe('BoundedCache', () => {
  it('evicts the least recently used entry once capacity is exceeded', () => {
    const cache = new BoundedCache<string, number>(2);
    cache.set('a', 1).set('b', 2);
    expect(cache.get('a')).toBe(1);

    cache.set('c', 3);

    expect(cache.has('a')).toBe(true);
    expect(cache.has('b')).toBe(false);
    expect(cache.get('c')).toBe(3);
    expect(cache.size).toBe(2);
  });

  it('updates an existing entry without growing the cache', () => {
    const cache = new BoundedCache<string, number>(2);
    cache.set('a', 1).set('a', 2);

    expect(cache.get('a')).toBe(2);
    expect(cache.size).toBe(1);
  });

  it('supports delete and clear', () => {
    const cache = new BoundedCache<string, number>(2);
    cache.set('a', 1).set('b', 2);
    expect(cache.delete('a')).toBe(true);
    cache.clear();
    expect(cache.size).toBe(0);
  });

  it('rejects invalid capacities', () => {
    expect(() => new BoundedCache(0)).toThrow(RangeError);
    expect(() => new BoundedCache(1.5)).toThrow(RangeError);
  });
});
