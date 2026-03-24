import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { queryApi } from '@/api/queryApi'
import type { QueryHistory } from '@/types/api'
import { cn } from '@/lib/utils'
import { Star, StarOff, ChevronDown, ChevronUp, Loader2, Clock, CheckCircle2, XCircle, AlertCircle } from 'lucide-react'

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  success: {
    label: 'success',
    color: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400',
    icon: <CheckCircle2 className="h-3 w-3" />,
  },
  error: {
    label: 'error',
    color: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-400',
    icon: <XCircle className="h-3 w-3" />,
  },
  pending: {
    label: 'pending',
    color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400',
    icon: <Clock className="h-3 w-3" />,
  },
  cancelled: {
    label: 'cancelled',
    color: 'bg-muted text-muted-foreground',
    icon: <AlertCircle className="h-3 w-3" />,
  },
}

function HistoryItem({ q, onToggleFavorite, favoriteLoading }: {
  q: QueryHistory
  onToggleFavorite: (id: string) => void
  favoriteLoading: boolean
}) {
  const [expanded, setExpanded] = useState(false)
  const status = STATUS_CONFIG[q.execution_status] ?? {
    label: q.execution_status,
    color: 'bg-muted text-muted-foreground',
    icon: null,
  }

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      {/* Header row */}
      <div className="flex items-center gap-2 px-4 py-3">
        {/* Favorite toggle */}
        <button
          onClick={(e) => { e.stopPropagation(); onToggleFavorite(q.id) }}
          disabled={favoriteLoading}
          className="shrink-0 p-1 rounded-lg hover:bg-accent transition-colors disabled:opacity-50"
          title={q.is_favorite ? 'Remove favorite' : 'Add favorite'}
        >
          {q.is_favorite
            ? <Star className="h-3.5 w-3.5 text-yellow-500 fill-yellow-500" />
            : <StarOff className="h-3.5 w-3.5 text-muted-foreground" />}
        </button>

        {/* Question text */}
        <button
          className="flex-1 text-left text-sm font-medium text-foreground truncate"
          onClick={() => setExpanded((v) => !v)}
        >
          {q.natural_language}
        </button>

        {/* Badges */}
        <div className="flex items-center gap-1.5 shrink-0">
          <span className={cn('flex items-center gap-1 px-2 py-0.5 text-[10px] font-medium rounded-full', status.color)}>
            {status.icon}
            {status.label}
          </span>
          {q.execution_time_ms != null && (
            <span className="px-2 py-0.5 text-[10px] bg-muted text-muted-foreground rounded-full">
              {q.execution_time_ms}ms
            </span>
          )}
          {q.row_count != null && (
            <span className="px-2 py-0.5 text-[10px] bg-muted text-muted-foreground rounded-full">
              {q.row_count} rows
            </span>
          )}
          <span className="text-[10px] text-muted-foreground w-28 text-right shrink-0">
            {new Date(q.created_at).toLocaleString()}
          </span>
          <button
            onClick={() => setExpanded((v) => !v)}
            className="p-1 rounded-lg hover:bg-accent text-muted-foreground transition-colors"
          >
            {expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
        </div>
      </div>

      {/* Expanded panel */}
      {expanded && (
        <div className="border-t border-border px-4 py-3 space-y-3 bg-muted/20">
          {q.final_sql && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1.5">SQL</p>
              <pre className="text-xs font-mono bg-background border border-border rounded-lg p-3 overflow-x-auto whitespace-pre-wrap leading-relaxed">
                {q.final_sql}
              </pre>
            </div>
          )}
          {q.error_message && (
            <div className="flex items-start gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-400">
              <XCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              {q.error_message}
            </div>
          )}
          {q.result_summary && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-1.5">Summary</p>
              <p className="text-sm text-foreground">{q.result_summary}</p>
            </div>
          )}
          {q.retry_count > 0 && (
            <span className="inline-flex px-2 py-0.5 text-[10px] font-medium rounded-full bg-yellow-100 text-yellow-700 dark:bg-yellow-900/40 dark:text-yellow-400">
              {q.retry_count} {q.retry_count === 1 ? 'retry' : 'retries'}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

export function HistoryPage() {
  const qc = useQueryClient()
  const [favoritesOnly, setFavoritesOnly] = useState(false)

  const { data: history, isLoading } = useQuery({
    queryKey: ['queryHistory'],
    queryFn: () => queryApi.history(),
  })

  const favoriteMutation = useMutation({
    mutationFn: (id: string) => queryApi.toggleFavorite(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['queryHistory'] }),
  })

  const displayed = favoritesOnly ? (history ?? []).filter((q) => q.is_favorite) : (history ?? [])

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
      <div className="max-w-3xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold text-foreground">Query History</h1>
          <button
            onClick={() => setFavoritesOnly((v) => !v)}
            className={cn(
              'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors',
              favoritesOnly
                ? 'bg-yellow-100 border-yellow-300 text-yellow-700 dark:bg-yellow-900/40 dark:border-yellow-700 dark:text-yellow-400'
                : 'border-border hover:bg-accent',
            )}
          >
            <Star className={cn('h-3.5 w-3.5', favoritesOnly ? 'fill-yellow-500 text-yellow-500' : '')} />
            {favoritesOnly ? 'All queries' : 'Favorites only'}
          </button>
        </div>

        {isLoading && (
          <div className="flex justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {!isLoading && displayed.length === 0 && (
          <div className="text-center py-12 border border-dashed border-border rounded-2xl">
            <Clock className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm text-muted-foreground">
              {favoritesOnly ? 'No favorited queries yet.' : 'No queries yet. Go ask a question!'}
            </p>
          </div>
        )}

        <div className="space-y-2">
          {displayed.map((q: QueryHistory) => (
            <HistoryItem
              key={q.id}
              q={q}
              onToggleFavorite={(id) => favoriteMutation.mutate(id)}
              favoriteLoading={favoriteMutation.isPending}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
