import { errorMessage } from '../data/mutationFeedback';
import { libraryData } from '../data/currentDataSource.svelte';
import type { AssetRelationshipOption, AssetSelectionTarget } from '../data/contracts';
import { LatestRequestController } from './latestRequest';

export class AssetRemovableRelationshipsController {
  albums = $state<AssetRelationshipOption[]>([]);
  tags = $state<AssetRelationshipOption[]>([]);
  loading = $state(false);
  error = $state('');
  private requests = new LatestRequestController();

  async load(target: AssetSelectionTarget): Promise<void> {
    const request = this.requests.begin();
    this.loading = true;
    this.error = '';
    try {
      const result = await libraryData.assets.removableRelationships(target, request.signal);
      if (!this.requests.isCurrent(request)) return;
      this.albums = result.albums;
      this.tags = result.tags;
    } catch (error) {
      if (this.requests.isCurrent(request)) {
        this.albums = [];
        this.tags = [];
        this.error = errorMessage(error, 'Linked relationships could not be loaded.');
      }
    } finally {
      if (this.requests.finish(request)) this.loading = false;
    }
  }

  cancel(): void {
    this.requests.cancel();
    this.loading = false;
  }

  destroy(): void {
    this.cancel();
  }
}
