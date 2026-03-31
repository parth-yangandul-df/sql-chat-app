import { useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { SpotlightTable } from '@/components/ui/spotlight-table'
import { Button } from '@/components/ui/button'
import type { QueryResult } from '@/types/api'
import { X } from 'lucide-react'

interface ResultsModalProps {
  result: QueryResult | null
  question: string
  onClose: () => void
}

export function ResultsModal({ result, question, onClose }: ResultsModalProps) {
  // Close on Escape key
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <AnimatePresence>
      {result && (
        <motion.div
          key="results-modal"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[99999] flex items-center justify-center"
        >
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* Modal card */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ type: 'spring', damping: 25, stiffness: 300 }}
            className="relative z-10 flex flex-col bg-background/90 backdrop-blur-xl border border-border/40 rounded-2xl shadow-2xl ring-1 ring-white/10 overflow-hidden"
            style={{ width: 'min(85vw, 1200px)', height: '85vh' }}
          >
            {/* Header */}
            <div className="relative shrink-0 border-b border-border/40 bg-muted/30 overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-primary/10 to-cyan-500/10 opacity-50" />
              <div className="relative z-10 flex items-start justify-between gap-4 px-5 py-4">
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-muted-foreground font-medium mb-0.5">Query results</p>
                  <p className="text-sm font-medium text-foreground leading-snug line-clamp-2">{question}</p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-xs text-muted-foreground">{result.row_count} rows</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7 rounded-lg hover:bg-background/50"
                    onClick={onClose}
                    aria-label="Close"
                  >
                    <X className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </div>

            {/* Table body */}
            <div className="flex-1 overflow-auto p-5 bg-gradient-to-b from-background/20 to-background/40">
              <SpotlightTable
                columns={result.columns}
                rows={result.rows}
                truncated={result.truncated}
                rowCount={result.row_count}
              />
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
