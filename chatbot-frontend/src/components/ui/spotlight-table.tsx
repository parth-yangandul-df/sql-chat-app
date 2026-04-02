import { useState, useMemo, useEffect } from 'react'
import { cn } from '@/lib/utils'
import { Download, ArrowUpDown, ArrowUp, ArrowDown, ChevronLeft, ChevronRight } from 'lucide-react'

interface SpotlightTableProps {
  columns: string[]
  rows: unknown[][]
  truncated?: boolean
  rowCount?: number
  className?: string
}

function exportCsv(columns: string[], rows: unknown[][]) {
  const escape = (v: unknown) =>
    `"${String(v ?? '').replace(/"/g, '""')}"`
  const header = columns.map(escape).join(',')
  const body = rows.map((r) => r.map(escape).join(',')).join('\n')
  const blob = new Blob([header + '\n' + body], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `results_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function getPaginationPages(page: number, totalPages: number): (number | '...')[] {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1)
  const pages: (number | '...')[] = [1]
  if (page > 3) pages.push('...')
  for (let i = Math.max(2, page - 1); i <= Math.min(totalPages - 1, page + 1); i++) {
    pages.push(i)
  }
  if (page < totalPages - 2) pages.push('...')
  pages.push(totalPages)
  return pages
}

export function SpotlightTable({ columns, rows, truncated, rowCount, className }: SpotlightTableProps) {
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [sortCol, setSortCol] = useState<number | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc' | null>(null)

  const lower = q.toLowerCase()

  function cycleSort(colIdx: number) {
    if (sortCol !== colIdx) {
      setSortCol(colIdx)
      setSortDir('asc')
    } else if (sortDir === 'asc') {
      setSortDir('desc')
    } else {
      setSortCol(null)
      setSortDir(null)
    }
  }

  const sortedRows = useMemo(() => {
    if (sortCol === null || sortDir === null) return rows
    return [...rows].sort((a, b) => {
      const av = a[sortCol]
      const bv = b[sortCol]
      const an = Number(av)
      const bn = Number(bv)
      const numericCompare = !isNaN(an) && !isNaN(bn)
      const cmp = numericCompare
        ? an - bn
        : String(av ?? '').localeCompare(String(bv ?? ''))
      return sortDir === 'asc' ? cmp : -cmp
    })
  }, [rows, sortCol, sortDir])

  // Global hard-filter across ALL rows before pagination
  const filteredRows = useMemo(() => {
    if (!lower) return sortedRows
    return sortedRows.filter((row) =>
      row.some((cell) => String(cell ?? '').toLowerCase().includes(lower)),
    )
  }, [sortedRows, lower])

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize))
  const safePage = Math.min(page, totalPages)
  const pagedRows = filteredRows.slice((safePage - 1) * pageSize, safePage * pageSize)

  const from = filteredRows.length === 0 ? 0 : (safePage - 1) * pageSize + 1
  const to = Math.min(safePage * pageSize, filteredRows.length)

  // Reset to page 1 when search term changes
  useEffect(() => {
    setPage(1)
  }, [q])

  // Reset to page 1 when page size changes
  useEffect(() => {
    setPage(1)
  }, [pageSize])

  if (columns.length === 0 || rows.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">No data returned.</p>
    )
  }

  return (
    <div className={cn('w-full', className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter rows..."
            className="flex-1 max-w-xs px-3 py-1.5 text-sm rounded-lg border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
          {lower && (
            <span className="text-xs text-muted-foreground whitespace-nowrap">
              {filteredRows.length} of {rows.length} rows match
            </span>
          )}
        </div>
        <button
          onClick={() => exportCsv(columns, rows)}
          className={cn(
            'flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg border border-input',
            'bg-background hover:bg-accent text-foreground transition-colors',
          )}
        >
          <Download className="h-3.5 w-3.5" />
          Export CSV
        </button>
      </div>

      {/* Table */}
      <div className="w-full overflow-x-auto rounded-lg border border-border">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50">
              {columns.map((col, colIdx) => (
                <th
                  key={col}
                  className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap"
                >
                  <button
                    onClick={() => cycleSort(colIdx)}
                    className="flex items-center gap-1 hover:text-foreground transition-colors"
                  >
                    {col}
                    {sortCol === colIdx && sortDir === 'asc' ? (
                      <ArrowUp className="h-3.5 w-3.5" />
                    ) : sortCol === colIdx && sortDir === 'desc' ? (
                      <ArrowDown className="h-3.5 w-3.5" />
                    ) : (
                      <ArrowUpDown className="h-3.5 w-3.5 opacity-40" />
                    )}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pagedRows.map((row, i) => (
              <tr
                key={i}
                className={cn(
                  'border-b border-border last:border-0 hover:bg-muted/30',
                  lower && 'bg-teal-50/50 dark:bg-teal-900/10',
                )}
              >
                {row.map((cell, j) => (
                  <td
                    key={j}
                    className="px-3 py-2 text-foreground whitespace-nowrap max-w-[200px] truncate"
                    title={String(cell ?? '')}
                  >
                    {cell === null || cell === undefined ? (
                      <span className="text-muted-foreground italic text-xs">null</span>
                    ) : (
                      String(cell)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-2">
          <span className="text-xs text-muted-foreground">
            Showing {from}–{to} of {filteredRows.length}
          </span>
          <div className="flex items-center gap-1">
            {/* Prev */}
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={safePage === 1}
              className={cn(
                'flex items-center justify-center w-7 h-7 rounded text-sm border border-input transition-colors',
                safePage === 1
                  ? 'opacity-40 cursor-not-allowed bg-background'
                  : 'bg-background hover:bg-accent',
              )}
              aria-label="Previous page"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>

            {/* Page numbers */}
            {getPaginationPages(safePage, totalPages).map((p, idx) =>
              p === '...' ? (
                <span key={`ellipsis-${idx}`} className="w-7 h-7 flex items-center justify-center text-xs text-muted-foreground">
                  …
                </span>
              ) : (
                <button
                  key={p}
                  onClick={() => setPage(p)}
                  className={cn(
                    'w-7 h-7 rounded text-xs border transition-colors',
                    p === safePage
                      ? 'bg-primary text-primary-foreground border-primary font-medium'
                      : 'bg-background border-input hover:bg-accent',
                  )}
                >
                  {p}
                </button>
              ),
            )}

            {/* Next */}
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={safePage === totalPages}
              className={cn(
                'flex items-center justify-center w-7 h-7 rounded text-sm border border-input transition-colors',
                safePage === totalPages
                  ? 'opacity-40 cursor-not-allowed bg-background'
                  : 'bg-background hover:bg-accent',
              )}
              aria-label="Next page"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between mt-1.5 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <span>{rowCount ?? rows.length} rows</span>
          {filteredRows.length > 10 && (
            <select
              value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}
              className="px-1.5 py-0.5 rounded border border-input bg-background text-foreground text-xs focus:outline-none focus:ring-1 focus:ring-ring"
            >
              <option value={10}>10 / page</option>
              <option value={25}>25 / page</option>
              <option value={50}>50 / page</option>
              <option value={100}>100 / page</option>
            </select>
          )}
        </div>
        {truncated && (
          <span className="text-amber-600 dark:text-amber-400">
            Results truncated — export CSV for full data
          </span>
        )}
      </div>
    </div>
  )
}
