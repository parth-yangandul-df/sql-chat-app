---
created: 2026-03-27T08:02:55.171Z
title: Add result table feature parity between frontend and chatbot-frontend
area: ui
files:
  - chatbot-frontend/src/components/ui/spotlight-table.tsx
  - frontend/src/pages/QueryPage.tsx
  - frontend/src/components/common/TablePagination.tsx
  - frontend/src/hooks/usePagination.ts
---

## Problem

The two frontends (`frontend/` using Mantine and `chatbot-frontend/` using Tailwind/shadcn) render query result tables with different feature sets. User asked for output to be identical in both.

Missing in `chatbot-frontend/src/components/ui/spotlight-table.tsx`:
- Pagination (currently renders all rows at once — no page size 10 slicing)
- Global hard-filter search (currently uses spotlight opacity approach; `frontend` was already fixed to hard-filter and paginate only matching rows)
- "X of Y rows match" counter next to search input
- Page reset to 1 on search term change

Missing in `frontend/src/pages/QueryPage.tsx`:
- Export CSV button (chatbot-frontend already has one in the toolbar)

Current feature matrix:

| Feature                          | frontend | chatbot-frontend |
|----------------------------------|----------|-----------------|
| Search bar (global hard-filter)  | ✅        | ❌ (opacity only) |
| "X of Y rows match" counter      | ✅        | ❌               |
| Sort toggle per column           | ✅        | ✅               |
| Pagination (page 10, numbered)   | ✅        | ❌               |
| Export CSV (full dataset)        | ❌        | ✅               |
| Highlighted rows when filtering  | ✅        | partial          |
| Truncation notice                | ✅        | ✅               |
| Null cell display                | ✅        | ✅               |

## Solution

### `chatbot-frontend/src/components/ui/spotlight-table.tsx`

1. Add `useEffect` import; `PAGE_SIZE = 10` constant at module level
2. Add `page` state; `filteredRows` memo (hard-filter `sortedRows` by `lower`); derive `pagedRows` via slice
3. `useEffect` to reset `page` to 1 when `q` changes
4. Replace `sortedRows.map(...)` in body with `pagedRows.map(...)`; drop opacity logic; add yellow bg class on all rows when `lower` active
5. Add `"X of Y rows match"` text next to search input when filtering
6. Add pagination UI below table — numbered page buttons with ellipsis and prev/next arrows matching Mantine `<Pagination size="sm">` layout; hidden when `totalPages <= 1`; "Showing X–Y of Z" on left, buttons on right

### `frontend/src/pages/QueryPage.tsx`

1. Add `exportCsv` helper (same logic as chatbot-frontend — CSV-escapes and downloads full `result.rows`)
2. Add `IconDownload` to `@tabler/icons-react` imports
3. Add Export CSV `Button` (`variant="default"`, `size="sm"`, `leftSection={<IconDownload size={14} />}`) in toolbar `Group` next to search input and match counter
