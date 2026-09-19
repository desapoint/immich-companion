import type { MediaResource } from '../types/libraryContracts';

export function mediaResourceSources(resource: MediaResource): string[] {
  return [...new Set([resource.url, ...resource.fallbackUrls].filter(Boolean))];
}

export function nextMediaSourceIndex(current: number, count: number): number | null {
  return current + 1 < count ? current + 1 : null;
}
