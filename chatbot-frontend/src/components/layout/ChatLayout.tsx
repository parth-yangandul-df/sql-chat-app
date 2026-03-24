import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { MessageSquare, Database, History, Bot } from 'lucide-react'
import { useEmbeddingStatus } from '@/hooks/useEmbeddingStatus'
import { useState } from 'react'

const NAV_ITEMS = [
  { label: 'Query', path: '/query', icon: MessageSquare },
  { label: 'Connections', path: '/connections', icon: Database },
  { label: 'History', path: '/history', icon: History },
]

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

export function ChatLayout() {
  const location = useLocation()
  const navigate = useNavigate()

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Sidebar */}
      <aside className="w-56 shrink-0 flex flex-col bg-card border-r border-border">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-border">
          <div className="flex items-center justify-center w-8 h-8 bg-primary rounded-lg">
            <Bot className="h-4 w-4 text-primary-foreground" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground leading-tight">QueryWise</p>
            <p className="text-[10px] text-muted-foreground leading-tight">AI Chat</p>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const active = location.pathname === item.path || (item.path === '/query' && location.pathname === '/')
            return (
              <button
                key={item.path}
                onClick={() => navigate(item.path)}
                className={cn(
                  'w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors text-left',
                  active
                    ? 'bg-primary text-primary-foreground'
                    : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                )}
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {item.label}
              </button>
            )
          })}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-border">
          <p className="text-[10px] text-muted-foreground">
            Ask anything in plain English
          </p>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <EmbeddingBanner />
        <Outlet />
      </div>
    </div>
  )
}
