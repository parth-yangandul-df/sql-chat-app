import { useState, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { MessageSquare, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { ChatPanel } from '@/components/widget/ChatPanel'
import { sessionApi } from '@/api/sessionApi'
import type { QueryResult, TurnContext } from '@/types/api'

// ── Types (lifted from ChatPanel so state survives panel unmount) ─────────────
export type ChatMessage =
  | { id: string; role: 'user'; content: string }
  | { id: string; role: 'assistant'; result: QueryResult }
  | { id: string; role: 'error'; message: string }

interface ChatWidgetProps {
  connectionId: string
}

// ── framer-motion variants ─────────────────────────────────────────────────────
const containerVariants = {
  hidden: {
    opacity: 0,
    y: 20,
    scale: 0.95,
    transformOrigin: 'bottom right',
  },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: {
      type: 'spring' as const,
      damping: 25,
      stiffness: 300,
    },
  },
  exit: {
    opacity: 0,
    y: 20,
    scale: 0.95,
    transition: { duration: 0.2 },
  },
}

// ── ChatWidget ────────────────────────────────────────────────────────────────
export function ChatWidget({ connectionId }: ChatWidgetProps) {
  const [open, setOpen] = useState(false)

  // Lifted state — survives panel AnimatePresence unmount/remount
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [overlayResult, setOverlayResult] = useState<QueryResult | null>(null)
  const [overlayQuestion, setOverlayQuestion] = useState<string>('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [lastTurnContext, setLastTurnContext] = useState<TurnContext | null>(null)

  // Auto-create session when connectionId is available
  useEffect(() => {
    if (!connectionId || sessionId) return
    sessionApi
      .create({ connection_id: connectionId })
      .then((session) => setSessionId(session.id))
      .catch(() => {}) // Non-fatal: session_id is optional in API
  }, [connectionId, sessionId])

  return (
    <div className="fixed bottom-6 right-6 z-[9999] flex flex-col items-end gap-3">
      {/* Animated chat panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            key="chat-panel"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
            exit="exit"
            style={{ width: 400, height: 600, transformOrigin: 'bottom right' }}
            className="flex flex-col"
          >
            <ChatPanel
              connectionId={connectionId}
              onClose={() => setOpen(false)}
              messages={messages}
              setMessages={setMessages}
              overlayResult={overlayResult}
              setOverlayResult={setOverlayResult}
              overlayQuestion={overlayQuestion}
              setOverlayQuestion={setOverlayQuestion}
              sessionId={sessionId}
              lastTurnContext={lastTurnContext}
              setLastTurnContext={setLastTurnContext}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Toggle button with framer-motion + glow blob */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Close QueryWise chat' : 'Open QueryWise chat'}
        className={cn(
          'cursor-pointer group relative flex h-14 w-14 items-center justify-center rounded-full shadow-2xl transition-all duration-300',
          open
            ? 'bg-destructive text-destructive-foreground rotate-90'
            : 'bg-primary text-primary-foreground hover:shadow-primary/25',
        )}
      >
        {/* Glow blob */}
        <span className="absolute inset-0 -z-10 rounded-full bg-inherit opacity-20 blur-xl transition-opacity duration-300 group-hover:opacity-40" />
        {open ? (
          <X className="h-6 w-6 text-white" />
        ) : (
          <MessageSquare className="h-6 w-6" />
        )}
      </motion.button>
    </div>
  )
}
