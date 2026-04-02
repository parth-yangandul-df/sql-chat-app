---
created: 2026-03-24T10:29:40.063Z
title: Paginate metadata tables and add CSV import
area: ui
files:
  - frontend/src/pages/Glossary.tsx
  - frontend/src/pages/Metrics.tsx
  - frontend/src/pages/Dictionary.tsx
  - frontend/src/pages/Knowledge.tsx
---

## Problem

The Glossary, Metrics, Dictionary, and Knowledge pages render all records in a single flat table with no pagination. As metadata grows (e.g. after seeding 43 dictionary entries), the tables become long and hard to navigate.

Additionally, there is no bulk import mechanism — users must add metadata one entry at a time via the UI form, which is impractical for seeding large datasets.

## Solution

1. **Pagination** — Add client-side or server-side pagination to all 4 metadata tables showing 15 records per page. Keep existing UI/layout intact; only add page controls (prev/next, page indicator). Check if backend list endpoints already support `limit`/`offset` params before deciding client vs server-side.

2. **CSV import button** (optional) — Add an "Import CSV" button to each of the 4 pages (Glossary, Metrics, Dictionary, Knowledge). On click, open a file picker, parse the CSV client-side, and POST each row to the respective API endpoint. Provide a sample CSV template or column header hint per page.
