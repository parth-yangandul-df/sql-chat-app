import { useRef, useEffect, useCallback, useState, type Dispatch, type SetStateAction } from 'react'
import { useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { queryApi, type ConversationTurn } from '@/api/queryApi'
import { PureMultimodalInput } from '@/components/ui/multimodal-ai-chat-input'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { RecentQuestions, saveRecentQuestion } from '@/components/widget/RecentQuestions'
import { ResultsModal } from '@/components/widget/ResultsModal'
import type { QueryResult, TurnContext } from '@/types/api'
import type { ChatMessage } from '@/components/widget/ChatWidget'
import { AlertCircle, Table, X } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Constants ──────────────────────────────────────────────────────────────────
const CONVERSATION_HISTORY_TURNS = 3

// ── framer-motion variants ─────────────────────────────────────────────────────
const messageVariants = {
  hidden: { opacity: 0, y: 10, x: -10 },
  visible: {
    opacity: 1,
    y: 0,
    x: 0,
    transition: { type: 'spring' as const, stiffness: 500, damping: 30 },
  },
}

// ── Build conversation history for API ─────────────────────────────────────────
function buildConversationHistory(messages: ChatMessage[]): ConversationTurn[] {
  const turns: ConversationTurn[] = []
  for (const msg of messages) {
    if (msg.role === 'user') {
      turns.push({ role: 'user', content: msg.content })
    } else if (msg.role === 'assistant') {
      // Include the generated SQL so the LLM can reference/filter/modify it on follow-ups.
      // This resolves pronouns like "them", "those", "it" by giving the LLM exact prior context.
      const sqlPart = msg.result.final_sql ? `SQL: ${msg.result.final_sql}\n` : ''
      const summaryPart =
        msg.result.summary ??
        (msg.result.row_count > 0 ? `Returned ${msg.result.row_count} rows.` : 'No results found.')
      turns.push({ role: 'assistant', content: sqlPart + summaryPart })
    }
  }
  const maxMessages = CONVERSATION_HISTORY_TURNS * 2
  return turns.slice(-maxMessages)
}

// ── Bot Avatar ─────────────────────────────────────────────────────────────────
function BotAvatar({ size = 'md' }: { size?: 'sm' | 'md' }) {
  return (
    <Avatar className={cn('border border-border/40 shadow-sm shrink-0', size === 'sm' ? 'h-7 w-7' : 'h-8 w-8')}>
      <AvatarFallback className="bg-primary/10 text-primary text-xs font-semibold">QW</AvatarFallback>
    </Avatar>
  )
}

// ── Assistant message bubble ───────────────────────────────────────────────────
function AssistantMessage({
  result,
  onViewResults,
}: {
  result: QueryResult
  onViewResults: (result: QueryResult) => void
}) {
  return (
    <motion.div variants={messageVariants} className="flex gap-3">
      <BotAvatar />
      <div className="flex-1 min-w-0 flex flex-col gap-1">
        <span className="text-xs font-medium text-muted-foreground">QueryWise</span>
        <div className="rounded-2xl rounded-tl-none bg-muted/50 px-4 py-2.5 text-sm shadow-sm backdrop-blur-sm border border-border/20 space-y-2">
          {result.summary && (
            <p className="leading-relaxed">{result.summary}</p>
          )}
          {/* highlights disabled */}
          {result.rows.length > 0 && (
            <button
              onClick={() => onViewResults(result)}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-border/40 bg-background/50 hover:bg-accent hover:text-accent-foreground transition-colors"
            >
              <Table className="h-3.5 w-3.5" />
              View full results
            </button>
          )}
        </div>
      </div>
    </motion.div>
  )
}

// ── User message bubble ────────────────────────────────────────────────────────
function UserMessage({ content }: { content: string }) {
  return (
    <motion.div variants={messageVariants} className="flex flex-row-reverse gap-3 self-end w-full">
      <Avatar className="h-8 w-8 border border-border/40 shadow-sm shrink-0">
        <AvatarFallback className="bg-primary text-primary-foreground text-xs font-semibold">ME</AvatarFallback>
      </Avatar>
      <div className="flex flex-col items-end gap-1 max-w-[80%]">
        <div className="rounded-2xl rounded-tr-none bg-primary px-4 py-2.5 text-sm text-primary-foreground shadow-md leading-relaxed">
          {content}
        </div>
      </div>
    </motion.div>
  )
}

// ── Error message ──────────────────────────────────────────────────────────────
function ErrorMessage({ message }: { message: string }) {
  return (
    <motion.div variants={messageVariants} className="flex gap-3">
      <div className="shrink-0 w-8 h-8 rounded-full bg-destructive/10 flex items-center justify-center">
        <AlertCircle className="h-3.5 w-3.5 text-destructive" />
      </div>
      <div className="flex-1 px-4 py-2.5 rounded-2xl rounded-tl-none bg-destructive/10 border border-destructive/20 backdrop-blur-sm">
        <p className="text-xs text-destructive font-medium mb-0.5">Error</p>
        <p className="text-xs text-destructive/80">{message}</p>
      </div>
    </motion.div>
  )
}

// ── Typing indicator — three bouncing dots ─────────────────────────────────────
function TypingIndicator() {
  return (
    <div className="flex gap-3">
      <BotAvatar />
      <div className="flex flex-col gap-1">
        <div className="rounded-2xl rounded-tl-none bg-muted/50 px-4 py-3 shadow-sm backdrop-blur-sm border border-border/20 w-16 flex items-center justify-center gap-1">
          <span className="h-1.5 w-1.5 rounded-full bg-foreground/40 animate-bounce [animation-delay:-0.3s]" />
          <span className="h-1.5 w-1.5 rounded-full bg-foreground/40 animate-bounce [animation-delay:-0.15s]" />
          <span className="h-1.5 w-1.5 rounded-full bg-foreground/40 animate-bounce" />
        </div>
      </div>
    </div>
  )
}

// ── Welcome screen ─────────────────────────────────────────────────────────────
function WelcomeScreen({ onSelect }: { onSelect: (q: string) => void }) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-6 p-6">
      <div className="text-center space-y-2">
        <div className="relative mx-auto w-12 h-12">
          <Avatar className="h-12 w-12 border-2 border-background shadow-sm">
            <AvatarFallback className="bg-primary/10 text-primary text-sm font-bold">QW</AvatarFallback>
          </Avatar>
          <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-background bg-emerald-500" />
        </div>
        <h2 className="text-base font-semibold text-foreground">How can I help you?</h2>
        <p className="text-xs text-muted-foreground max-w-xs">
          Ask questions about your data in plain English.
        </p>
      </div>
      <RecentQuestions onSelect={onSelect} />
    </div>
  )
}

// ── ChatPanel props — now a controlled component ───────────────────────────────
interface ChatPanelProps {
  connectionId: string
  onClose: () => void
  messages: ChatMessage[]
  setMessages: Dispatch<SetStateAction<ChatMessage[]>>
  overlayResult: QueryResult | null
  setOverlayResult: Dispatch<SetStateAction<QueryResult | null>>
  overlayQuestion: string
  setOverlayQuestion: Dispatch<SetStateAction<string>>
  sessionId: string | null
  lastTurnContext: TurnContext | null
  setLastTurnContext: Dispatch<SetStateAction<TurnContext | null>>
}

// ── ChatPanel ─────────────────────────────────────────────────────────────────
export function ChatPanel({
  connectionId,
  onClose,
  messages,
  setMessages,
  overlayResult,
  setOverlayResult,
  overlayQuestion,
  setOverlayQuestion,
  sessionId,
  lastTurnContext,
  setLastTurnContext,
}: ChatPanelProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const [attachments, setAttachments] = useState<{ url: string; name: string; contentType: string; size: number }[]>([])

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const mutation = useMutation({
    mutationFn: ({ question, history }: { question: string; history: ConversationTurn[] }) =>
      queryApi.execute({
        connection_id: connectionId,
        question,
        session_id: sessionId ?? undefined,
        conversation_history: history,
        last_turn_context: lastTurnContext ?? undefined,
      }),
    onSuccess: (result) => {
      setLastTurnContext(result.turn_context)   // store for next request
      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-assistant`, role: 'assistant', result },
      ])
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : 'An unexpected error occurred'
      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-error`, role: 'error', message },
      ])
    },
  })

  const sendMessage = useCallback(
    (content: string) => {
      if (!content.trim() || !connectionId || mutation.isPending) return

      const trimmed = content.trim()
      saveRecentQuestion(trimmed)

      const userMsg: ChatMessage = {
        id: `${Date.now()}-user`,
        role: 'user',
        content: trimmed,
      }

      const history = buildConversationHistory(messages)
      setMessages((prev) => [...prev, userMsg])
      mutation.mutate({ question: trimmed, history })
    },
    [connectionId, messages, mutation, setMessages],
  )

  const handleViewResults = useCallback(
    (result: QueryResult) => {
      setMessages((prev) => {
        const assistantIdx = prev.findIndex(
          (m) => m.role === 'assistant' && (m as Extract<ChatMessage, { role: 'assistant' }>).result === result,
        )
        const userMsg = assistantIdx > 0 ? prev[assistantIdx - 1] : null
        const question =
          userMsg?.role === 'user' ? userMsg.content : result.question ?? 'Query results'
        setOverlayQuestion(question)
        return prev
      })
      setOverlayResult(result)
    },
    [setMessages, setOverlayResult, setOverlayQuestion],
  )

  const hasMessages = messages.length > 0

  return (
    <>
      {/* Glassmorphism panel */}
      <div className="flex flex-col h-full min-h-0 overflow-hidden rounded-2xl border border-border/40 bg-background/60 shadow-2xl backdrop-blur-xl ring-1 ring-white/10">

        {/* Header */}
        <div className="relative shrink-0 border-b border-border/40 bg-muted/30 p-4 overflow-hidden">
          {/* Gradient overlay — QueryWise brand teal */}
          <div className="absolute inset-0 bg-gradient-to-br from-primary/20 to-cyan-500/20 opacity-50" />
          <div className="relative z-10 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="relative">
                <Avatar className="h-10 w-10 border-2 border-background shadow-sm">
                  <AvatarFallback className="bg-primary/10 text-primary text-sm font-bold">QW</AvatarFallback>
                </Avatar>
                {/* Online status dot */}
                <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-background bg-emerald-500" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-foreground">QueryWise</h3>
                <p className="text-xs text-muted-foreground">Data assistant · online</p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-full hover:bg-background/50"
              onClick={onClose}
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto bg-gradient-to-b from-background/20 to-background/40">
          {!hasMessages ? (
            <WelcomeScreen onSelect={sendMessage} />
          ) : (
            <motion.div
              className="px-4 py-4 space-y-4"
              initial="hidden"
              animate="visible"
              variants={{ visible: { transition: { staggerChildren: 0.05 } } }}
            >
              {messages.map((msg) => {
                if (msg.role === 'user') {
                  return <UserMessage key={msg.id} content={msg.content} />
                }
                if (msg.role === 'assistant') {
                  return (
                    <AssistantMessage
                      key={msg.id}
                      result={msg.result}
                      onViewResults={handleViewResults}
                    />
                  )
                }
                return <ErrorMessage key={msg.id} message={msg.message} />
              })}
              {mutation.isPending && <TypingIndicator />}
              <div ref={messagesEndRef} />
            </motion.div>
          )}
        </div>

        {/* Input area */}
        <div className="shrink-0 border-t border-border/40 bg-background/60 px-3 py-3 backdrop-blur-md">
          <PureMultimodalInput
            chatId="widget"
            messages={[]}
            attachments={attachments}
            setAttachments={setAttachments}
            onSendMessage={({ input }) => sendMessage(input)}
            onStopGenerating={() => {}}
            isGenerating={mutation.isPending}
            canSend={!!connectionId && !mutation.isPending}
            hideSuggestions={true}
          />
          <p className="text-center text-[10px] text-muted-foreground mt-1.5">
            Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>

      {/* Results overlay — outside panel so it covers full viewport */}
      {overlayResult && (
        <ResultsModal
          result={overlayResult}
          question={overlayQuestion}
          onClose={() => setOverlayResult(null)}
        />
      )}
    </>
  )
}
