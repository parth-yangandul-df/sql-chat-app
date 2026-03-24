import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Download } from 'lucide-react'

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

export function SpotlightTable({ columns, rows, truncated, rowCount, className }: SpotlightTableProps) {
  const [q, setQ] = useState('')
  const lower = q.toLowerCase()

  if (columns.length === 0 || rows.length === 0) {
    return (
      <p className="text-sm text-muted-foreground italic">No data returned.</p>
    )
  }

  return (
    <div className={cn('w-full', className)}>
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-3 mb-3">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Filter rows..."
          className="flex-1 max-w-xs px-3 py-1.5 text-sm rounded-lg border border-input bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
        />
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
              {columns.map((col) => (
                <th
                  key={col}
                  className="px-3 py-2 text-left font-medium text-muted-foreground whitespace-nowrap"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const hit =
                lower !== '' &&
                row.some((cell) =>
                  String(cell ?? '').toLowerCase().includes(lower),
                )
              return (
                <tr
                  key={i}
                  className={cn(
                    'border-b border-border last:border-0 transition-opacity',
                    'hover:bg-muted/30',
                    hit
                      ? 'opacity-100 bg-yellow-50/50 dark:bg-yellow-900/10'
                      : q
                        ? 'opacity-25'
                        : 'opacity-100',
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
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between mt-1.5 text-xs text-muted-foreground">
        <span>{rowCount ?? rows.length} rows</span>
        {truncated && (
          <span className="text-amber-600 dark:text-amber-400">
            Results truncated — export CSV for full data
          </span>
        )}
      </div>
    </div>
  )
}
