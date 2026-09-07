export class V2NotImplementedError extends Error {
  readonly code = 'V2_NOT_IMPLEMENTED';
  readonly operation: string;

  constructor(operation: string) {
    super(`Implementation not done yet: ${operation}`);
    this.name = 'V2NotImplementedError';
    this.operation = operation;
  }
}

export function notImplemented(operation: string): never {
  throw new V2NotImplementedError(operation);
}

export function isV2NotImplementedError(value: unknown): value is V2NotImplementedError {
  return value instanceof V2NotImplementedError
    || (value instanceof Error && (value as Error & { code?: string }).code === 'V2_NOT_IMPLEMENTED');
}
