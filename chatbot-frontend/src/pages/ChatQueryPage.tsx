import { useState, useRef, useEffect, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import { queryApi } from '@/api/queryApi'
import { useConnections } from '@/hooks/useConnections'
import { PromptBox } from '@/components/ui/chatgpt-prompt-input'
import { SpotlightTable } from '@/components/ui/spotlight-table'
import { MorphLoading } from '@/components/ui/morph-loading'
import { cn } from '@/lib/utils'
import type { QueryResult } from '@/types/api'
import { Bot, User, AlertCircle, ChevronDown, ChevronUp, Copy, Check, Zap } from 'lucide-react'

// ── Message types ──────────────────────────────────────────────────────────────
type ChatMessage =
  | { id: string; role: 'user'; content: string }
  | { id: string; role: 'assistant'; result: QueryResult }
  | { id: string; role: 'error'; message: string }

// ── SQL collapsible block ──────────────────────────────────────────────────────
function SqlBlock({ sql }: { sql: string }) {
  const [open, setOpen] = useState(false)
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    void navigator.clipboard.writeText(sql)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="mt-3 rounded-lg border border-border overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 bg-muted/50 hover:bg-muted text-xs font-medium text-muted-foreground transition-colors"
      >
        <span className="flex items-center gap-1.5">
          <Zap className="h-3 w-3" />
          View generated SQL
        </span>
        {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>
      {open && (
        <div className="relative">
          <pre className="p-3 text-xs font-mono bg-card text-foreground overflow-x-auto whitespace-pre-wrap leading-relaxed">
            {sql}
          </pre>
          <button
            onClick={handleCopy}
            className="absolute top-2 right-2 p-1 rounded bg-muted hover:bg-accent transition-colors"
            title="Copy SQL"
          >
            {copied ? <Check className="h-3 w-3 text-green-500" /> : <Copy className="h-3 w-3 text-muted-foreground" />}
          </button>
        </div>
      )}
    </div>
  )
}

// ── Assistant message bubble ───────────────────────────────────────────────────
function AssistantMessage({
  result,
  onFollowup,
}: {
  result: QueryResult
  onFollowup: (q: string) => void
}) {
  return (
    <div className="flex gap-3 group">
      {/* Avatar */}
      <div className="shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center">
        <Bot className="h-4 w-4 text-primary-foreground" />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 space-y-3">
        {/* Summary */}
        {result.summary && (
          <p className="text-sm text-foreground leading-relaxed">{result.summary}</p>
        )}

        {/* Highlights */}
        {result.highlights.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {result.highlights.map((h, i) => (
              <span
                key={i}
                className="px-2 py-0.5 text-xs rounded-full bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300 font-medium"
              >
                {h}
              </span>
            ))}
          </div>
        )}

        {/* Meta badges */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>{result.row_count} rows</span>
          <span>·</span>
          <span>{result.execution_time_ms}ms</span>
          {result.retry_count > 0 && (
            <>
              <span>·</span>
              <span className="text-amber-500">{result.retry_count} retries</span>
            </>
          )}
        </div>

        {/* Data table */}
        {result.rows.length > 0 && (
          <SpotlightTable
            columns={result.columns}
            rows={result.rows}
            truncated={result.truncated}
            rowCount={result.row_count}
          />
        )}

        {/* SQL accordion */}
        {result.final_sql && <SqlBlock sql={result.final_sql} />}

        {/* Suggested followups */}
        {result.suggested_followups.length > 0 && (
          <div className="pt-1">
            <p className="text-xs text-muted-foreground mb-2 font-medium">Continue exploring:</p>
            <div className="flex flex-wrap gap-2">
              {result.suggested_followups.map((q, i) => (
                <button
                  key={i}
                  onClick={() => onFollowup(q)}
                  className="px-3 py-1.5 text-xs rounded-full border border-border bg-background hover:bg-accent hover:text-accent-foreground transition-colors text-left"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── User message bubble ────────────────────────────────────────────────────────
function UserMessage({ content }: { content: string }) {
  return (
    <div className="flex gap-3 justify-end group">
      <div className="max-w-[75%]">
        <div className="px-4 py-2.5 rounded-2xl rounded-tr-sm bg-primary text-primary-foreground text-sm leading-relaxed">
          {content}
        </div>
      </div>
      <div className="shrink-0 w-8 h-8 rounded-full bg-secondary flex items-center justify-center">
        <User className="h-4 w-4 text-secondary-foreground" />
      </div>
    </div>
  )
}

// ── Error message ──────────────────────────────────────────────────────────────
function ErrorMessage({ message }: { message: string }) {
  return (
    <div className="flex gap-3">
      <div className="shrink-0 w-8 h-8 rounded-full bg-destructive/10 flex items-center justify-center">
        <AlertCircle className="h-4 w-4 text-destructive" />
      </div>
      <div className="flex-1 px-4 py-2.5 rounded-2xl rounded-tl-sm bg-destructive/10 border border-destructive/20">
        <p className="text-sm text-destructive font-medium mb-0.5">Error</p>
        <p className="text-sm text-destructive/80">{message}</p>
      </div>
    </div>
  )
}

// ── Typing indicator ───────────────────────────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="flex gap-3 items-center">
      <div className="shrink-0 w-8 h-8 rounded-full bg-primary flex items-center justify-center">
        <Bot className="h-4 w-4 text-primary-foreground" />
      </div>
      <div className="flex items-center gap-2 px-4 py-3 rounded-2xl rounded-tl-sm bg-muted">
        <MorphLoading size="sm" className="w-10 h-10" />
        <span className="text-xs text-muted-foreground">Analyzing your question...</span>
      </div>
    </div>
  )
}

// ── Welcome screen ─────────────────────────────────────────────────────────────
function WelcomeScreen({ onExample }: { onExample: (q: string) => void }) {
  const examples = [
    'What is the total ECL by stage?',
    'Show me the top 10 counterparties by exposure',
    'How many facilities are past due?',
    'What is the average PD by rating?',
  ]

  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-8 p-8">
      <div className="text-center space-y-3">
        <div className="flex items-center justify-center w-16 h-16 mx-auto bg-primary rounded-2xl shadow-lg">
          <Bot className="h-8 w-8 text-primary-foreground" />
        </div>
        <h1 className="text-2xl font-semibold text-foreground">How can I help you?</h1>
        <p className="text-sm text-muted-foreground max-w-md">
          Ask questions about your data in plain English. I'll generate SQL, execute it, and explain the results.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
        {examples.map((ex, i) => (
          <button
            key={i}
            onClick={() => onExample(ex)}
            className="px-4 py-3 text-sm text-left rounded-xl border border-border bg-card hover:bg-accent hover:text-accent-foreground transition-colors leading-snug"
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  )
}

// ── Main ChatQueryPage ─────────────────────────────────────────────────────────
export function ChatQueryPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [connectionId, setConnectionId] = useState<string | null>(null)
  const [pendingMessage, setPendingMessage] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const promptRef = useRef<HTMLTextAreaElement>(null)

  const { data: connections, isLoading: loadingConns } = useConnections()

  // Auto-select first connection
  useEffect(() => {
    if (!connectionId && connections && connections.length > 0) {
      setConnectionId(connections[0].id)
    }
  }, [connections, connectionId])

  // Scroll to bottom on new messages
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const mutation = useMutation({
    mutationFn: ({ question, connId }: { question: string; connId: string }) =>
      queryApi.execute({ connection_id: connId, question }),
    onSuccess: (result, { question }) => {
      const id = `${Date.now()}-assistant`
      setMessages((prev) => [
        ...prev.filter((m) => !(m.role === 'user' && m.content === question && prev.indexOf(m) === prev.length - 1)),
        ...prev.slice(-1)[0]?.role === 'user' ? [] : [],
        { id, role: 'assistant', result },
      ])
      setPendingMessage(null)
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'An unexpected error occurred'
      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-error`, role: 'error', message },
      ])
      setPendingMessage(null)
    },
  })

  const sendMessage = useCallback(
    (content: string) => {
      if (!content.trim() || !connectionId || mutation.isPending) return

      const userMsg: ChatMessage = {
        id: `${Date.now()}-user`,
        role: 'user',
        content: content.trim(),
      }
      setMessages((prev) => [...prev, userMsg])
      setPendingMessage(content.trim())
      mutation.mutate({ question: content.trim(), connId: connectionId })
    },
    [connectionId, mutation],
  )

  const handleFollowup = useCallback(
    (q: string) => {
      sendMessage(q)
    },
    [sendMessage],
  )

  const hasMessages = messages.length > 0

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Top bar */}
      <div className="shrink-0 flex items-center justify-between gap-3 px-4 py-2 border-b border-border bg-card/50 backdrop-blur-sm">
        <h1 className="text-sm font-semibold text-foreground">Chat</h1>
        <div className="flex items-center gap-2">
          {loadingConns ? (
            <div className="h-8 w-44 bg-muted animate-pulse rounded-lg" />
          ) : (
            <select
              value={connectionId ?? ''}
              onChange={(e) => setConnectionId(e.target.value || null)}
              className={cn(
                'h-8 px-3 text-xs rounded-lg border border-input bg-background text-foreground',
                'focus:outline-none focus:ring-2 focus:ring-ring',
                'disabled:opacity-50',
              )}
            >
              {(!connections || connections.length === 0) && (
                <option value="" disabled>No connections — add one first</option>
              )}
              {connections?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
          {connectionId && (
            <span
              className={cn(
                'px-2 py-0.5 text-[10px] font-medium rounded-full',
                connections?.find((c) => c.id === connectionId)?.is_active
                  ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-400'
                  : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
              )}
            >
              {connections?.find((c) => c.id === connectionId)?.is_active ? 'Active' : 'Inactive'}
            </span>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {!hasMessages ? (
          <WelcomeScreen onExample={sendMessage} />
        ) : (
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
            {messages.map((msg) => {
              if (msg.role === 'user') {
                return <UserMessage key={msg.id} content={msg.content} />
              }
              if (msg.role === 'assistant') {
                return (
                  <AssistantMessage
                    key={msg.id}
                    result={msg.result}
                    onFollowup={handleFollowup}
                  />
                )
              }
              return <ErrorMessage key={msg.id} message={msg.message} />
            })}

            {mutation.isPending && pendingMessage && (
              <TypingIndicator />
            )}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="shrink-0 border-t border-border bg-card/50 backdrop-blur-sm px-4 py-3">
        <div className="max-w-3xl mx-auto">
          {!connectionId && !loadingConns && (
            <p className="text-xs text-amber-600 dark:text-amber-400 mb-2 text-center">
              Add and select a database connection above to start querying.
            </p>
          )}
          <PromptBox
            ref={promptRef}
            onSend={sendMessage}
            loading={mutation.isPending}
            disabled={!connectionId || mutation.isPending}
          />
          <p className="text-center text-[10px] text-muted-foreground mt-2">
            Press Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  )
}
