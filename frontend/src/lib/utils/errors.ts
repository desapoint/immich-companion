export function errorMessage(error: unknown): string {
  return error instanceof Error && error.message
    ? error.message
    : 'An unexpected frontend error interrupted the page.';
}
