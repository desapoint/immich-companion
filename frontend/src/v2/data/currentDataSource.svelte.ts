import { createDemoLibraryDataSource } from './demo/demoLibraryDataSource.svelte';
import { withDemoMediaProfiles } from './demo/demoMediaProfile';

// Single composition point for the V2 UI. Replacing this with an API-backed
// implementation should not require page/component changes.
export const libraryData = withDemoMediaProfiles(createDemoLibraryDataSource());
