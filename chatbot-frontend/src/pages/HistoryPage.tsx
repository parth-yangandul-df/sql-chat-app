import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { sessionApi } from '@/api/sessionApi'
import { useConnections } from '@/hooks/useConnections'
import type { ChatSession, Connection } from '@/types/api'
import { cn } from '@/lib/utils'
import { History, MessageSquare, Loader2, Database } from 'lucide-react'

// ── Relative time helper ───────────────────────────────────────────────────────
function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

// ── Session card ───────────────────────────────────────────────────────────────
function SessionCard({
  session,
  connectionName,
  onClick,
}: {
  session: ChatSession
  connectionName: string
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full flex items-start gap-3 px-4 py-3.5 rounded-xl border border-border bg-card',
        'hover:border-primary/40 hover:bg-accent/50 transition-colors text-left group',
      )}
    >
      <div className="shrink-0 mt-0.5 flex items-center justify-center w-7 h-7 rounded-lg bg-primary/10 text-primary">
        <MessageSquare className="h-3.5 w-3.5" />
      </div>

      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-foreground truncate leading-snug group-hover:text-primary transition-colors">
          {session.title}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
            <Database className="h-2.5 w-2.5 shrink-0" />
            {connectionName}
          </span>
          {session.message_count > 0 && (
            <span className="text-[10px] text-muted-foreground">
              · {session.message_count} {session.message_count === 1 ? 'message' : 'messages'}
            </span>
          )}
        </div>
      </div>

      <div className="shrink-0 text-right">
        <p className="text-[10px] text-muted-foreground">{relativeTime(session.updated_at)}</p>
      </div>
    </button>
  )
}

// ── Sessions grouped by connection ─────────────────────────────────────────────
function SessionGroup({
  connection,
  sessions,
  onOpen,
}: {
  connection: Connection
  sessions: ChatSession[]
  onOpen: (sessionId: string) => void
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 px-1">
        <Database className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide truncate">
          {connection.name}
        </h2>
        <span className="text-[10px] text-muted-foreground">({sessions.length})</span>
      </div>
      <div className="space-y-1.5">
        {sessions.map((s) => (
          <SessionCard
            key={s.id}
            session={s}
            connectionName={connection.name}
            onClick={() => onOpen(s.id)}
          />
        ))}
      </div>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────
export function HistoryPage() {
  const navigate = useNavigate()
  const { data: connections, isLoading: connectionsLoading } = useConnections()

  // Fetch all sessions (no connection_id filter) to show full history
  const { data: sessions, isLoading: sessionsLoading } = useQuery({
    queryKey: ['threads'],
    queryFn: () => sessionApi.list(),
    staleTime: 10_000,
  })

  const isLoading = connectionsLoading || sessionsLoading

  // Build a map of connectionId → Connection for label lookup
  const connectionMap = new Map<string, Connection>(
    (connections ?? []).map((c) => [c.id, c]),
  )

  // Group sessions by connection_id, preserving most-recent-first order
  const grouped = new Map<string, ChatSession[]>()
  for (const s of sessions ?? []) {
    const bucket = grouped.get(s.connection_id)
    if (bucket) bucket.push(s)
    else grouped.set(s.connection_id, [s])
  }

  const totalSessions = sessions?.length ?? 0

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-2">
          <History className="h-5 w-5 text-foreground" />
          <h1 className="text-xl font-semibold text-foreground">History</h1>
          {totalSessions > 0 && (
            <span className="ml-1 px-2 py-0.5 text-[10px] font-medium rounded-full bg-muted text-muted-foreground">
              {totalSessions} {totalSessions === 1 ? 'session' : 'sessions'}
            </span>
          )}
        </div>

        {/* Loading */}
        {isLoading && (
          <div className="flex justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {/* Empty state */}
        {!isLoading && totalSessions === 0 && (
          <div className="text-center py-16 border border-dashed border-border rounded-2xl">
            <MessageSquare className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
            <p className="text-sm font-medium text-foreground mb-1">No chat sessions yet</p>
            <p className="text-xs text-muted-foreground">
              Start a conversation in the chat to see your history here.
            </p>
          </div>
        )}

        {/* Session groups */}
        {!isLoading && totalSessions > 0 && (
          <div className="space-y-6">
            {Array.from(grouped.entries()).map(([connectionId, groupSessions]) => {
              const connection = connectionMap.get(connectionId)
              if (!connection) return null
              return (
                <SessionGroup
                  key={connectionId}
                  connection={connection}
                  sessions={groupSessions}
                  onOpen={(id) => navigate(`/query/${id}`)}
                />
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
