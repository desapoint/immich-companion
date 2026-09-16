import { actualSizeZoom, anchoredPan, clampPan, renderedSize } from './viewerViewport';

export class ViewerViewportController {
  zoom = $state(1);
  panX = $state(0);
  panY = $state(0);
  naturalWidth = $state(800);
  naturalHeight = $state(600);
  viewport = $state<HTMLElement | null>(null);

  readonly minZoom: number;
  readonly maxZoom: number;

  constructor(minZoom = 0.1, maxZoom = 8) {
    this.minZoom = minZoom;
    this.maxZoom = maxZoom;
  }

  get transform(): string {
    return `translate(${this.panX}px, ${this.panY}px) scale(${this.zoom})`;
  }

  setViewport(viewport: HTMLElement | null): void {
    this.viewport = viewport;
  }

  setNaturalSize(width: number, height: number): void {
    if (width > 0) this.naturalWidth = width;
    if (height > 0) this.naturalHeight = height;
  }

  fit(): void {
    this.zoom = 1;
    this.panX = 0;
    this.panY = 0;
  }

  actual(): void {
    if (!this.viewport) {
      this.fit();
      return;
    }
    const rect = this.viewport.getBoundingClientRect();
    this.zoom = actualSizeZoom(
      rect.width,
      rect.height,
      this.naturalWidth,
      this.naturalHeight,
      this.minZoom,
      this.maxZoom,
    );
    this.panX = 0;
    this.panY = 0;
  }

  clamp(): void {
    if (!this.viewport) return;
    const rect = this.viewport.getBoundingClientRect();
    const size = renderedSize(
      rect.width,
      rect.height,
      this.naturalWidth,
      this.naturalHeight,
      this.zoom,
    );
    const next = clampPan(this.panX, this.panY, size);
    this.panX = next.x;
    this.panY = next.y;
  }

  setZoom(next: number, anchorX: number | null = null, anchorY: number | null = null): void {
    const previous = this.zoom;
    const nextZoom = Math.max(this.minZoom, Math.min(this.maxZoom, next));
    if (anchorX !== null && anchorY !== null) {
      const nextPan = anchoredPan(this.panX, this.panY, previous, nextZoom, anchorX, anchorY);
      this.panX = nextPan.x;
      this.panY = nextPan.y;
    }
    this.zoom = nextZoom;
    this.clamp();
  }

  panBy(deltaX: number, deltaY: number): void {
    this.panX += deltaX;
    this.panY += deltaY;
    this.clamp();
  }

  wheel(event: WheelEvent): void {
    if (!this.viewport) return;
    const rect = this.viewport.getBoundingClientRect();
    const anchorX = event.clientX - rect.left - rect.width / 2;
    const anchorY = event.clientY - rect.top - rect.height / 2;
    this.setZoom(this.zoom * (event.deltaY < 0 ? 1.12 : 1 / 1.12), anchorX, anchorY);
  }
}
