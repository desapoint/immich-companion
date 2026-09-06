export interface PageResult<T> {
  items: T[];
  page: number;
  pageSize: number;
  pages: number;
  total: number;
}
