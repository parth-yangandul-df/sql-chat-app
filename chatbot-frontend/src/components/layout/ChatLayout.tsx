import { Outlet, useLocation, useNavigate, useParams } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { Database, History, Bot, Plus, Trash2, MessageSquare } from 'lucide-react'
import { useEmbeddingStatus } from '@/hooks/useEmbeddingStatus'
import { useConnections } from '@/hooks/useConnections'
import { useThreads, useCreateThread, useDeleteThread } from '@/hooks/useThreads'
import { useState, useEffect, useRef } from 'react'
import type { ChatSession } from '@/types/api'

// ── Embedding progress banner ──────────────────────────────────────────────────
function EmbeddingBanner() {
  const { data } = useEmbeddingStatus()
  const [dismissed, setDismissed] = useState<Set<string>>(new Set())

  if (!data) return null
  const activeTasks = data.tasks.filter(
    (t) => (t.status === 'running' || t.status === 'pending') && !dismissed.has(t.connection_id),
  )
  if (activeTasks.length === 0) return null

  return (
    <div className="px-4 pt-2 space-y-2">
      {activeTasks.map((task) => {
        const pct = task.total > 0 ? Math.round((task.completed / task.total) * 100) : 0
        return (
          <div
            key={task.connection_id}
            className="flex items-center gap-3 px-3 py-2 bg-blue-50 dark:bg-blue-950/30 border border-blue-200 dark:border-blue-800 rounded-lg text-xs"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <span className="text-blue-700 dark:text-blue-300">Generating embeddings...</span>
                <span className="text-blue-500">{task.completed}/{task.total}</span>
              </div>
              <div className="h-1 bg-blue-200 dark:bg-blue-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
            <button
              onClick={() => setDismissed((prev) => new Set(prev).add(task.connection_id))}
              className="text-blue-400 hover:text-blue-600 shrink-0"
            >
              ✕
            </button>
          </div>
        )
      })}
    </div>
  )
}

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

// ── Thread list item ───────────────────────────────────────────────────────────
function ThreadItem({
  session,
  active,
  connectionId,
  onNavigate,
}: {
  session: ChatSession
  active: boolean
  connectionId: string
  onNavigate: (id: string) => void
}) {
  const [hovered, setHovered] = useState(false)
  const deleteThread = useDeleteThread()

  const handleDelete = (e: React.MouseEvent) => {
    e.stopPropagation()
    deleteThread.mutate({ id: session.id, connection_id: connectionId })
  }

  return (
    <button
      onClick={() => onNavigate(session.id)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      className={cn(
        'w-full flex items-start gap-2 px-3 py-2 rounded-lg text-left transition-colors group relative',
        active
          ? 'bg-gray-100 text-gray-900'
          : 'text-gray-500 hover:bg-gray-100 hover:text-gray-900',
      )}
    >
      <MessageSquare className="h-3.5 w-3.5 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className={cn(
          'text-xs font-medium truncate leading-snug',
          active ? 'text-gray-900' : '',
        )}>
          {session.title}
        </p>
        <p className="text-[10px] text-muted-foreground mt-0.5">
          {relativeTime(session.updated_at)}
          {session.message_count > 0 && ` · ${session.message_count} msg`}
        </p>
      </div>
      {hovered && !deleteThread.isPending && (
        <button
          onClick={handleDelete}
          className="shrink-0 p-0.5 rounded hover:bg-destructive/10 hover:text-destructive transition-colors"
          title="Delete thread"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      )}
    </button>
  )
}

// ── Thread sidebar section ────────────────────────────────────────────────────
function ThreadSidebar({
  connectionId,
  activeThreadId,
}: {
  connectionId: string
  activeThreadId: string | undefined
}) {
  const navigate = useNavigate()
  const { data: threads, isLoading } = useThreads(connectionId)
  const createThread = useCreateThread()

  const handleNewChat = async () => {
    const session = await createThread.mutateAsync({ connection_id: connectionId })
    navigate(`/query/${session.id}`)
  }

  return (
    <div className="flex flex-col min-h-0 flex-1">
      {/* New Chat button */}
      <div className="px-2 pt-2 pb-1">
        <button
          onClick={() => { void handleNewChat() }}
          disabled={createThread.isPending}
          className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium bg-gray-900 text-white hover:bg-gray-700 transition-colors disabled:opacity-60"
        >
          <Plus className="h-3.5 w-3.5" />
          New Chat
        </button>
      </div>

      {/* Thread list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
        {isLoading && (
          <div className="px-3 py-2 text-[10px] text-muted-foreground">Loading...</div>
        )}
        {!isLoading && (!threads || threads.length === 0) && (
          <div className="px-3 py-4 text-center text-[10px] text-muted-foreground leading-relaxed">
            No chats yet.<br />Click "New Chat" to start.
          </div>
        )}
        {threads?.map((session) => (
          <ThreadItem
            key={session.id}
            session={session}
            active={session.id === activeThreadId}
            connectionId={connectionId}
            onNavigate={(id) => navigate(`/query/${id}`)}
          />
        ))}
      </div>
    </div>
  )
}

// ── Bottom nav items ──────────────────────────────────────────────────────────
const BOTTOM_NAV = [
  { label: 'Connections', path: '/connections', icon: Database },
  { label: 'History', path: '/history', icon: History },
]

// ── Outlet context type ───────────────────────────────────────────────────────
export interface ChatLayoutContext {
  connectionId: string
  setConnectionId: (id: string) => void
}

// ── Main layout ────────────────────────────────────────────────────────────────
export function ChatLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { threadId } = useParams<{ threadId?: string }>()
  const { data: connections } = useConnections()
  const createThread = useCreateThread()
  const autoCreating = useRef(false)

  // Active connection persists in localStorage across navigations
  const [connectionId, setConnectionIdState] = useState<string>(() => {
    return localStorage.getItem('querywise_active_connection') ?? ''
  })

  // Auto-select first connection if none stored
  useEffect(() => {
    if (!connectionId && connections && connections.length > 0) {
      const id = connections[0].id
      setConnectionIdState(id)
      localStorage.setItem('querywise_active_connection', id)
    }
  }, [connections, connectionId])

  // Auto-create thread when landing on /query with no threadId
  useEffect(() => {
    if (connectionId && !threadId && location.pathname === '/query' && !autoCreating.current) {
      autoCreating.current = true
      createThread.mutateAsync({ connection_id: connectionId })
        .then((session) => { navigate(`/query/${session.id}`, { replace: true }) })
        .catch(() => { /* leave on /query — user can click New Chat manually */ })
        .finally(() => { autoCreating.current = false })
    }
  }, [connectionId, threadId, location.pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleConnectionChange = (id: string) => {
    setConnectionIdState(id)
    localStorage.setItem('querywise_active_connection', id)
  }

  return (
    <div className="flex h-screen bg-white overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 flex flex-col bg-white border-r border-gray-200">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-gray-200 shrink-0">
          <div className="flex items-center justify-center w-8 h-8 bg-gray-900 rounded-lg">
            <Bot className="h-4 w-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-gray-900 leading-tight">QueryWise</p>
            <p className="text-[10px] text-gray-400 leading-tight">AI Chat</p>
          </div>
        </div>

        {/* Connection selector */}
        <div className="px-3 py-2 border-b border-gray-200 shrink-0">
          <select
            value={connectionId}
            onChange={(e) => handleConnectionChange(e.target.value)}
            className="w-full h-7 px-2 text-xs rounded-md border border-gray-300 bg-white text-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-500"
          >
            {(!connections || connections.length === 0) && (
              <option value="" disabled>No connections</option>
            )}
            {connections?.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>

        {/* Thread list */}
        <div className="flex-1 flex flex-col min-h-0">
          {connectionId ? (
            <ThreadSidebar connectionId={connectionId} activeThreadId={threadId} />
          ) : (
            <div className="flex-1 flex items-center justify-center px-4">
              <p className="text-[10px] text-muted-foreground text-center leading-relaxed">
                Select a connection to see your chat threads.
              </p>
            </div>
          )}
        </div>

        {/* Bottom nav */}
        <nav className="shrink-0 px-2 py-2 border-t border-gray-200 space-y-0.5">
          {BOTTOM_NAV.map((item) => {
            const active = location.pathname === item.path
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={cn(
                  'w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left',
                  active
                    ? 'bg-gray-100 text-gray-900'
                    : 'text-gray-500 hover:bg-gray-100 hover:text-gray-900',
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {item.label}
              </button>
            )
          })}
        </nav>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <EmbeddingBanner />
        <Outlet context={{ connectionId, setConnectionId: handleConnectionChange } satisfies ChatLayoutContext} />
      </div>
    </div>
  )
}
