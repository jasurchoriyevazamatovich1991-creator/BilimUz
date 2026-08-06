/**
 * Shared pagination meta shape — verified identical across users,
 * tests, attempts, and results routers (grep-checked against the real
 * backend source, all four use the exact same
 * `{page, per_page, total, total_pages}` dict literal).
 */
export interface PaginatedMeta {
  page: number;
  per_page: number;
  total: number;
  total_pages: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  meta: PaginatedMeta;
}
