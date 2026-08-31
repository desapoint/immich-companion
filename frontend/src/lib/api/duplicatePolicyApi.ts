import type { DuplicatePolicy, ImmichLibraryOption } from '../types/duplicatePolicy';

async function requestJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    ...init,
    headers: { accept: 'application/json', ...init?.headers },
  });
  if (!response.ok) throw new Error(`Could not load duplicate policy (${response.status}).`);
  return await response.json() as T;
}

export function loadDuplicatePolicy(): Promise<DuplicatePolicy> {
  return requestJson('/api/settings/duplicates/policy');
}

export function saveDuplicatePolicy(policy: DuplicatePolicy): Promise<DuplicatePolicy> {
  return requestJson('/api/settings/duplicates/policy', {
    method: 'PUT',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(policy),
  });
}

export function loadImmichLibraries(): Promise<ImmichLibraryOption[]> {
  return requestJson('/api/settings/duplicates/libraries');
}
