export type ComparisonImageLoadHandler = (event: Event) => void;
export type ComparisonImageErrorHandler = () => void;

export interface ComparisonImageAsset {
  src: string;
  label: string;
  onload?: ComparisonImageLoadHandler;
  onerror?: ComparisonImageErrorHandler;
}

export interface ComparisonImagePair {
  selected: ComparisonImageAsset;
  reference: ComparisonImageAsset;
}
