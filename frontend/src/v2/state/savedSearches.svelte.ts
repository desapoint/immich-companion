import { libraryData } from '../data/currentDataSource.svelte';
import { errorMessage, mutationFeedback, type OperationFeedback } from '../data/mutationFeedback';
import type { AssetSearchCriteria, SavedSearchCreateInput, SavedSearchRecord, SavedSearchUpdateInput } from '../data/contracts';

export class SavedSearchController {
  records = $state<SavedSearchRecord[]>([]);
  loading = $state(false);
  busy = $state(false);
  error = $state('');
  feedback = $state<OperationFeedback | null>(null);
  query = $state('');

  async refresh(query = this.query): Promise<void> {
    if (this.loading) return;
    this.loading = true;
    this.query = query;
    try {
      const result = await libraryData.savedSearches.search({ query, pageSize: 100, sort: { field: 'name', direction: 'asc' } });
      this.records = result.items;
      this.error = '';
    } catch (error) {
      this.error = errorMessage(error, 'Saved searches could not be loaded.');
    } finally {
      this.loading = false;
    }
  }

  async get(id: string): Promise<SavedSearchRecord | undefined> {
    try {
      const record = await libraryData.savedSearches.getById(id);
      this.error = '';
      return record;
    } catch (error) {
      this.error = errorMessage(error, 'Saved search could not be loaded.');
      return undefined;
    }
  }

  async create(input: SavedSearchCreateInput): Promise<SavedSearchRecord | undefined> {
    if (this.busy) return undefined;
    this.busy = true;
    try {
      const record = await libraryData.savedSearches.create(input);
      this.feedback = { tone: 'ok', title: 'Saved search created', detail: `Saved “${record.name}”.`, failures: [] };
      this.error = '';
      await this.refresh(this.query);
      return record;
    } catch (error) {
      this.error = errorMessage(error, 'Saved search could not be created.');
      return undefined;
    } finally {
      this.busy = false;
    }
  }

  async update(id: string, patch: SavedSearchUpdateInput): Promise<boolean> {
    if (this.busy) return false;
    this.busy = true;
    try {
      const result = await libraryData.savedSearches.update(id, patch);
      this.feedback = mutationFeedback('Update saved search', result);
      this.error = result.failed.length ? result.failed.map((failure) => failure.reason).join(' · ') : '';
      await this.refresh(this.query);
      return result.failed.length === 0;
    } catch (error) {
      this.error = errorMessage(error, 'Saved search could not be updated.');
      return false;
    } finally {
      this.busy = false;
    }
  }

  async delete(id: string): Promise<boolean> {
    if (this.busy) return false;
    this.busy = true;
    try {
      const result = await libraryData.savedSearches.delete([id]);
      this.feedback = mutationFeedback('Delete saved search', result);
      this.error = result.failed.length ? result.failed.map((failure) => failure.reason).join(' · ') : '';
      await this.refresh(this.query);
      return result.failed.length === 0;
    } catch (error) {
      this.error = errorMessage(error, 'Saved search could not be deleted.');
      return false;
    } finally {
      this.busy = false;
    }
  }

  async saveCurrent(name: string, description: string, criteria: AssetSearchCriteria): Promise<SavedSearchRecord | undefined> {
    return this.create({ name, description, criteria });
  }
}
