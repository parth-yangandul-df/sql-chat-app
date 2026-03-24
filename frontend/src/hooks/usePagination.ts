import { useState } from 'react';

const PAGE_SIZE = 15;

export function usePagination<T>(items: T[] | undefined) {
  const [page, setPage] = useState(1);

  const total = items?.length ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Reset to page 1 if current page exceeds total (e.g. after delete)
  const safePage = Math.min(page, totalPages);

  const paged = items?.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE) ?? [];

  return {
    page: safePage,
    setPage,
    totalPages,
    total,
    paged,
    pageSize: PAGE_SIZE,
  };
}
