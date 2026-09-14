export class BoundedCache<K, V> {
  readonly capacity: number;
  readonly #entries = new Map<K, V>();

  constructor(capacity: number) {
    if (!Number.isInteger(capacity) || capacity <= 0) {
      throw new RangeError('BoundedCache capacity must be a positive integer.');
    }
    this.capacity = capacity;
  }

  get size(): number {
    return this.#entries.size;
  }

  has(key: K): boolean {
    return this.#entries.has(key);
  }

  get(key: K): V | undefined {
    const value = this.#entries.get(key);
    if (value === undefined && !this.#entries.has(key)) return undefined;
    this.#entries.delete(key);
    this.#entries.set(key, value as V);
    return value;
  }

  set(key: K, value: V): this {
    this.#entries.delete(key);
    this.#entries.set(key, value);
    while (this.#entries.size > this.capacity) {
      const oldestKey = this.#entries.keys().next().value as K | undefined;
      if (oldestKey === undefined) break;
      this.#entries.delete(oldestKey);
    }
    return this;
  }

  delete(key: K): boolean {
    return this.#entries.delete(key);
  }

  clear(): void {
    this.#entries.clear();
  }
}
