import { renderPixelDifference } from '../mediaDifference';
import type {
  AssetRecord,
  AssetSearchCriteria,
  DuplicateGroupRecord,
  LegacyMediaRepository,
  LibraryDataSource,
  MediaAsset,
  MediaResource,
  PageResult,
  ResolvedLibraryDataSource,
  SavedSearchRepository,
  TrashAssetRecord,
  TrashSearchCriteria,
  ViewerNavigationWindow,
} from '../contracts';

type MediaResolvedLibraryDataSource = Omit<ResolvedLibraryDataSource, 'savedSearches'> & { readonly savedSearches?: SavedSearchRepository };
const RAW_EXTENSIONS = ['dng', 'nef', 'cr3', 'arw', 'raf'] as const;
function ordinal(id: string): number { const tail = id.match(/-([0-9a-f]{12})$/i)?.[1]; return tail ? Number.parseInt(tail, 16) : 0; }
function replaceExtension(name: string, extension: string): string { return `${name.replace(/\.[^.]+$/, '')}.${extension}`; }
function profileAsset(asset: AssetRecord): AssetRecord {
  const index = Math.max(0, ordinal(asset.id) - 1); const profiled = index % 43 === 17 ? { ...asset, is_offline: true } : asset;
  if (profiled.asset_type === 'VIDEO') { const variant = Math.floor(index / 11) % 4; if (variant === 1) return { ...profiled, original_file_name: replaceExtension(profiled.original_file_name, 'mov'), original_mime_type: 'video/quicktime; codecs=hvc1' }; if (variant === 2) return { ...profiled, original_file_name: replaceExtension(profiled.original_file_name, 'webm'), original_mime_type: 'video/webm; codecs=vp9' }; if (variant === 3) return { ...profiled, original_file_name: replaceExtension(profiled.original_file_name, 'mkv'), original_mime_type: 'video/x-matroska; codecs=av01' }; return { ...profiled, original_mime_type: 'video/mp4; codecs=avc1.42E01E' }; }
  if (profiled.asset_type === 'IMAGE') { if (index % 29 === 7) return { ...profiled, original_file_name: replaceExtension(profiled.original_file_name, 'heic'), original_mime_type: 'image/heic' }; if (index % 31 === 9) { const ext = RAW_EXTENSIONS[Math.floor(index / 31) % RAW_EXTENSIONS.length]; const mime = ext === 'dng' ? 'image/x-adobe-dng' : `image/x-${ext}`; return { ...profiled, original_file_name: replaceExtension(profiled.original_file_name, ext), original_mime_type: mime }; } if (index % 37 === 13) return { ...profiled, original_file_name: replaceExtension(profiled.original_file_name, 'avif'), original_mime_type: 'image/avif' }; }
  return profiled;
}
function profileTrash(asset: TrashAssetRecord): TrashAssetRecord { const index = Math.max(0, ordinal(asset.id) - 1); if (asset.type === 'VIDEO') { const variant = Math.floor(index / 11) % 4; if (variant === 1) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'mov'), original_mime_type: 'video/quicktime; codecs=hvc1' }; if (variant === 2) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'webm'), original_mime_type: 'video/webm; codecs=vp9' }; if (variant === 3) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'mkv'), original_mime_type: 'video/x-matroska; codecs=av01' }; } else if (asset.type === 'IMAGE') { if (index % 29 === 7) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'heic'), original_mime_type: 'image/heic' }; if (index % 31 === 9) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'dng'), original_mime_type: 'image/x-adobe-dng' }; } return asset; }
function profilePage<T>(page: PageResult<T>, map: (item: T) => T): PageResult<T> { return { ...page, items: page.items.map(map) }; }
function profileDuplicateGroup(group: DuplicateGroupRecord): DuplicateGroupRecord { return { ...group, members: group.members.map((member) => ({ ...member, asset: profileAsset(member.asset) })) }; }
function mediaType(asset: MediaAsset): AssetRecord['asset_type'] { return 'asset_type' in asset ? asset.asset_type : asset.type; }
function mimeForUrl(url: string, fallback: string | null): string | null { if (url.startsWith('data:image/svg+xml')) return 'image/svg+xml'; if (/\.jpe?g(?:$|\?)/i.test(url)) return 'image/jpeg'; if (/\.png(?:$|\?)/i.test(url)) return 'image/png'; if (/\.webp(?:$|\?)/i.test(url)) return 'image/webp'; if (/\.mp4(?:$|\?)/i.test(url)) return 'video/mp4'; return fallback; }
function needsDecodedImage(asset: MediaAsset): boolean { const mime = asset.original_mime_type?.toLowerCase() ?? ''; return mediaType(asset) === 'IMAGE' && (mime.includes('heic') || mime.includes('heif') || mime.includes('x-adobe-dng') || mime.includes('x-nef') || mime.includes('x-cr3') || mime.includes('x-arw') || mime.includes('x-raf')); }
function needsTranscodedVideo(asset: MediaAsset): boolean { const mime = asset.original_mime_type?.toLowerCase() ?? ''; return mediaType(asset) === 'VIDEO' && !(mime.startsWith('video/mp4') && mime.includes('avc1')); }
function resource(url: string, asset: MediaAsset, delivery: MediaResource['delivery'], posterUrl: string | null = null): MediaResource { return { url, mimeType: mimeForUrl(url, asset.original_mime_type), posterUrl, delivery, originalMimeType: asset.original_mime_type, expiresAt: null }; }
async function locateNavigation<T extends { id: string }>(currentId: string, fetchPage: (cursor: string | null) => Promise<PageResult<T>>): Promise<ViewerNavigationWindow> { let cursor: string | null = null; let previousId: string | null = null; let offset = 0; while (true) { const page = await fetchPage(cursor); const index = page.items.findIndex((item) => item.id === currentId); if (index >= 0) { let nextId = page.items[index + 1]?.id ?? null; if (!nextId && page.nextCursor) { const following = await fetchPage(page.nextCursor); nextId = following.items[0]?.id ?? null; } return { previousId: page.items[index - 1]?.id ?? previousId, nextId, position: offset + index + 1, total: page.total }; } if (page.items.length) previousId = page.items.at(-1)?.id ?? previousId; offset += page.items.length; if (!page.nextCursor) return { previousId: null, nextId: null, position: null, total: page.total }; cursor = page.nextCursor; } }

export function withDemoMediaProfiles(source: LibraryDataSource): MediaResolvedLibraryDataSource {
  const legacyMedia = source.media as LegacyMediaRepository;
  let lastAssetCriteria: AssetSearchCriteria = { mode: 'simple', filters: {}, sort: { field: 'takenDate', direction: 'desc' } };
  let lastTrashCriteria: TrashSearchCriteria = { sort: { field: 'deletedAt', direction: 'desc' } };
  const thumbnail = (asset: MediaAsset): MediaResource => { const url = mediaType(asset) === 'VIDEO' ? '/demo-fixtures/video-poster.jpg' : legacyMedia.thumbnail(asset); return resource(url, asset, 'thumbnail'); };
  const view = (asset: MediaAsset): MediaResource => { if (mediaType(asset) === 'VIDEO') return resource('/demo-fixtures/clip.mp4', asset, needsTranscodedVideo(asset) ? 'transcoded' : 'original', '/demo-fixtures/video-poster.jpg'); const url = legacyMedia.fullSize(asset); return resource(url, asset, needsDecodedImage(asset) ? 'decoded' : 'preview'); };
  const assets = { ...source.assets, async getById(id: string) { const asset = await source.assets.getById(id); return asset ? profileAsset(asset) : undefined; }, async getMany(ids: readonly string[]) { return (await source.assets.getMany(ids)).map(profileAsset); }, async getTrashById(id: string) { const asset = await source.assets.getTrashById(id); return asset ? profileTrash(asset) : undefined; }, async search(query: Parameters<typeof source.assets.search>[0]) { lastAssetCriteria = query; return profilePage(await source.assets.search(query), profileAsset); }, async searchTrash(query: Parameters<typeof source.assets.searchTrash>[0]) { lastTrashCriteria = query; return profilePage(await source.assets.searchTrash(query), profileTrash); } };
  return { ...source, assets, duplicates: { ...source.duplicates, async search(query) { return profilePage(await source.duplicates.search(query), profileDuplicateGroup); } }, navigation: { async asset(currentId) { return locateNavigation(currentId, async (cursor) => assets.search({ ...lastAssetCriteria, pageSize: 100, cursor })); }, async trash(currentId) { return locateNavigation(currentId, async (cursor) => assets.searchTrash({ ...lastTrashCriteria, pageSize: 100, cursor })); } }, media: { thumbnail, view, async difference(selected, reference, options = {}) { if (selected.asset_type !== 'IMAGE' || reference.asset_type !== 'IMAGE') throw new Error('Pixel difference is only available for images.'); return renderPixelDifference(view(selected), view(reference), options); }, async refresh(asset, purpose) { return purpose === 'thumbnail' ? thumbnail(asset) : view(asset); } } };
}
