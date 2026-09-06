import { renderPixelDifference } from '../mediaDifference';
import type {
  AssetRecord,
  DuplicateGroupRecord,
  LegacyMediaRepository,
  LibraryDataSource,
  MediaAsset,
  MediaResource,
  PageResult,
  ResolvedLibraryDataSource,
  TrashAssetRecord,
} from '../contracts';

const RAW_EXTENSIONS = ['dng', 'nef', 'cr3', 'arw', 'raf'] as const;

function ordinal(id: string): number {
  const tail = id.match(/-([0-9a-f]{12})$/i)?.[1];
  return tail ? Number.parseInt(tail, 16) : 0;
}

function replaceExtension(name: string, extension: string): string {
  return `${name.replace(/\.[^.]+$/, '')}.${extension}`;
}

function profileAsset(asset: AssetRecord): AssetRecord {
  const index = Math.max(0, ordinal(asset.id) - 1);
  if (asset.asset_type === 'VIDEO') {
    const variant = Math.floor(index / 11) % 4;
    if (variant === 1) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'mov'), original_mime_type: 'video/quicktime; codecs=hvc1' };
    if (variant === 2) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'webm'), original_mime_type: 'video/webm; codecs=vp9' };
    if (variant === 3) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'mkv'), original_mime_type: 'video/x-matroska; codecs=av01' };
    return { ...asset, original_mime_type: 'video/mp4; codecs=avc1.42E01E' };
  }

  if (asset.asset_type === 'IMAGE') {
    if (index % 29 === 7) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'heic'), original_mime_type: 'image/heic' };
    if (index % 31 === 9) {
      const ext = RAW_EXTENSIONS[Math.floor(index / 31) % RAW_EXTENSIONS.length];
      const mime = ext === 'dng' ? 'image/x-adobe-dng' : `image/x-${ext}`;
      return { ...asset, original_file_name: replaceExtension(asset.original_file_name, ext), original_mime_type: mime };
    }
    if (index % 37 === 13) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'avif'), original_mime_type: 'image/avif' };
  }
  return asset;
}

function profileTrash(asset: TrashAssetRecord): TrashAssetRecord {
  const index = Math.max(0, ordinal(asset.id) - 1);
  if (asset.type === 'VIDEO') {
    const variant = Math.floor(index / 11) % 4;
    if (variant === 1) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'mov'), original_mime_type: 'video/quicktime; codecs=hvc1' };
    if (variant === 2) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'webm'), original_mime_type: 'video/webm; codecs=vp9' };
    if (variant === 3) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'mkv'), original_mime_type: 'video/x-matroska; codecs=av01' };
  } else if (asset.type === 'IMAGE') {
    if (index % 29 === 7) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'heic'), original_mime_type: 'image/heic' };
    if (index % 31 === 9) return { ...asset, original_file_name: replaceExtension(asset.original_file_name, 'dng'), original_mime_type: 'image/x-adobe-dng' };
  }
  return asset;
}

function profilePage<T>(page: PageResult<T>, map: (item: T) => T): PageResult<T> {
  return { ...page, items: page.items.map(map) };
}

function profileDuplicateGroup(group: DuplicateGroupRecord): DuplicateGroupRecord {
  return { ...group, members: group.members.map((member) => ({ ...member, asset: profileAsset(member.asset) })) };
}

function mediaType(asset: MediaAsset): AssetRecord['asset_type'] {
  return 'asset_type' in asset ? asset.asset_type : asset.type;
}

function mimeForUrl(url: string, fallback: string | null): string | null {
  if (url.startsWith('data:image/svg+xml')) return 'image/svg+xml';
  if (/\.jpe?g(?:$|\?)/i.test(url)) return 'image/jpeg';
  if (/\.png(?:$|\?)/i.test(url)) return 'image/png';
  if (/\.webp(?:$|\?)/i.test(url)) return 'image/webp';
  if (/\.mp4(?:$|\?)/i.test(url)) return 'video/mp4';
  return fallback;
}

function needsDecodedImage(asset: MediaAsset): boolean {
  const mime = asset.original_mime_type?.toLowerCase() ?? '';
  return mediaType(asset) === 'IMAGE' && (
    mime.includes('heic') || mime.includes('heif') || mime.includes('x-adobe-dng') || mime.includes('x-nef') ||
    mime.includes('x-cr3') || mime.includes('x-arw') || mime.includes('x-raf')
  );
}

function needsTranscodedVideo(asset: MediaAsset): boolean {
  const mime = asset.original_mime_type?.toLowerCase() ?? '';
  return mediaType(asset) === 'VIDEO' && !(mime.startsWith('video/mp4') && mime.includes('avc1'));
}

function resource(
  url: string,
  asset: MediaAsset,
  delivery: MediaResource['delivery'],
  posterUrl: string | null = null,
): MediaResource {
  return {
    url,
    mimeType: mimeForUrl(url, asset.original_mime_type),
    posterUrl,
    delivery,
    originalMimeType: asset.original_mime_type,
    expiresAt: null,
  };
}

export function withDemoMediaProfiles(source: LibraryDataSource): ResolvedLibraryDataSource {
  const legacyMedia = source.media as LegacyMediaRepository;
  const thumbnail = (asset: MediaAsset): MediaResource => {
    const url = mediaType(asset) === 'VIDEO' ? '/demo-fixtures/video-poster.jpg' : legacyMedia.thumbnail(asset);
    return resource(url, asset, 'thumbnail');
  };
  const view = (asset: MediaAsset): MediaResource => {
    if (mediaType(asset) === 'VIDEO') {
      return resource('/demo-fixtures/clip.mp4', asset, needsTranscodedVideo(asset) ? 'transcoded' : 'original', '/demo-fixtures/video-poster.jpg');
    }
    const url = legacyMedia.fullSize(asset);
    return resource(url, asset, needsDecodedImage(asset) ? 'decoded' : 'preview');
  };

  return {
    ...source,
    assets: {
      ...source.assets,
      async getById(id) { const asset = await source.assets.getById(id); return asset ? profileAsset(asset) : undefined; },
      async getMany(ids) { return (await source.assets.getMany(ids)).map(profileAsset); },
      async getTrashById(id) { const asset = await source.assets.getTrashById(id); return asset ? profileTrash(asset) : undefined; },
      async search(query) { return profilePage(await source.assets.search(query), profileAsset); },
      async searchTrash(query) { return profilePage(await source.assets.searchTrash(query), profileTrash); },
    },
    duplicates: {
      ...source.duplicates,
      async search(query) { return profilePage(await source.duplicates.search(query), profileDuplicateGroup); },
    },
    media: {
      thumbnail,
      view,
      async difference(selected, reference, options = {}) {
        if (selected.asset_type !== 'IMAGE' || reference.asset_type !== 'IMAGE') throw new Error('Pixel difference is only available for images.');
        return renderPixelDifference(view(selected), view(reference), options);
      },
      async refresh(asset, purpose) {
        return purpose === 'thumbnail' ? thumbnail(asset) : view(asset);
      },
    },
  };
}
