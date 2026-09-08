import type { DifferenceOptions, MediaResource } from './contracts';

const MAX_DIMENSION = 1200;
const imageCache = new Map<string, Promise<HTMLImageElement>>();

function loadImage(url: string): Promise<HTMLImageElement> {
  const cached = imageCache.get(url);
  if (cached) return cached;
  const pending = new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.decoding = 'async';
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`Unable to load comparison image: ${url}`));
    image.src = url;
  });
  imageCache.set(url, pending);
  void pending.catch(() => imageCache.delete(url));
  return pending;
}

async function loadResourceImage(resource: MediaResource): Promise<HTMLImageElement> {
  const urls = [...new Set([resource.url, ...resource.fallbackUrls].filter(Boolean))];
  for (const url of urls) {
    try {
      return await loadImage(url);
    } catch {
      // Continue through the same ordered fallbacks used by the media viewer.
    }
  }
  throw new Error(`Unable to load comparison image: ${resource.url}`);
}

function fitDimensions(width: number, height: number): { width: number; height: number } {
  const scale = Math.min(1, MAX_DIMENSION / Math.max(width, height));
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
}

function containedRect(
  sourceWidth: number,
  sourceHeight: number,
  targetWidth: number,
  targetHeight: number,
): { x: number; y: number; width: number; height: number } {
  const scale = Math.min(targetWidth / sourceWidth, targetHeight / sourceHeight);
  const width = Math.max(1, sourceWidth * scale);
  const height = Math.max(1, sourceHeight * scale);
  return {
    x: (targetWidth - width) / 2,
    y: (targetHeight - height) / 2,
    width,
    height,
  };
}

function drawContained(
  context: CanvasRenderingContext2D,
  image: HTMLImageElement,
  width: number,
  height: number,
): void {
  context.clearRect(0, 0, width, height);
  const rect = containedRect(image.naturalWidth, image.naturalHeight, width, height);
  context.drawImage(image, rect.x, rect.y, rect.width, rect.height);
}

function hueRgb(hue: number): [number, number, number] {
  const h = ((hue % 360) + 360) % 360;
  const c = 1;
  const x = 1 - Math.abs((h / 60) % 2 - 1);
  let rgb: [number, number, number];
  if (h < 60) rgb = [c, x, 0];
  else if (h < 120) rgb = [x, c, 0];
  else if (h < 180) rgb = [0, c, x];
  else if (h < 240) rgb = [0, x, c];
  else if (h < 300) rgb = [x, 0, c];
  else rgb = [c, 0, x];
  return rgb.map((value) => Math.round(value * 255)) as [number, number, number];
}

export async function renderPixelDifference(
  selected: MediaResource,
  reference: MediaResource,
  options: DifferenceOptions = {},
): Promise<MediaResource> {
  const [selectedImage, referenceImage] = await Promise.all([
    loadResourceImage(selected),
    loadResourceImage(reference),
  ]);
  const naturalWidth = Math.max(selectedImage.naturalWidth, referenceImage.naturalWidth);
  const naturalHeight = Math.max(selectedImage.naturalHeight, referenceImage.naturalHeight);
  const { width, height } = fitDimensions(naturalWidth, naturalHeight);

  const selectedCanvas = document.createElement('canvas');
  const referenceCanvas = document.createElement('canvas');
  selectedCanvas.width = referenceCanvas.width = width;
  selectedCanvas.height = referenceCanvas.height = height;
  const selectedContext = selectedCanvas.getContext('2d', { willReadFrequently: true });
  const referenceContext = referenceCanvas.getContext('2d', { willReadFrequently: true });
  if (!selectedContext || !referenceContext) throw new Error('2D canvas is unavailable for difference rendering.');

  drawContained(selectedContext, selectedImage, width, height);
  drawContained(referenceContext, referenceImage, width, height);

  const selectedPixels = selectedContext.getImageData(0, 0, width, height);
  const referencePixels = referenceContext.getImageData(0, 0, width, height);
  const output = selectedContext.createImageData(width, height);
  const contrast = Math.max(0.1, (options.contrast ?? 100) / 100);
  const binary = options.binary ?? false;
  const tint = hueRgb(options.hue ?? 190);

  for (let index = 0; index < output.data.length; index += 4) {
    const red = Math.abs(selectedPixels.data[index] - referencePixels.data[index]);
    const green = Math.abs(selectedPixels.data[index + 1] - referencePixels.data[index + 1]);
    const blue = Math.abs(selectedPixels.data[index + 2] - referencePixels.data[index + 2]);
    const alphaDifference = Math.abs(selectedPixels.data[index + 3] - referencePixels.data[index + 3]);
    const delta = Math.min(255, Math.max(red, green, blue, alphaDifference) * contrast);
    const strength = binary ? (delta >= 12 ? 1 : 0) : delta / 255;
    output.data[index] = Math.round(tint[0] * strength);
    output.data[index + 1] = Math.round(tint[1] * strength);
    output.data[index + 2] = Math.round(tint[2] * strength);
    output.data[index + 3] = 255;
  }

  selectedContext.putImageData(output, 0, 0);
  return {
    url: selectedCanvas.toDataURL('image/png'),
    fallbackUrls: [],
    mimeType: 'image/png',
    posterUrl: null,
    delivery: 'difference',
    originalMimeType: null,
    expiresAt: null,
  };
}
