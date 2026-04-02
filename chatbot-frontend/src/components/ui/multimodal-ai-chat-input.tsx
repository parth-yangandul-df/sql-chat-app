'use client';

import React, {
  useRef,
  useEffect,
  useState,
  useCallback,
  type Dispatch,
  type SetStateAction,
  type ChangeEvent,
  memo,
} from 'react';

import equal from 'fast-deep-equal';
import { AnimatePresence, motion } from 'framer-motion';
import { Loader2 as LoaderIcon, X as XIcon } from 'lucide-react';
import { cva, type VariantProps } from 'class-variance-authority';
import { twMerge } from 'tailwind-merge';

const clsx = (...args: unknown[]) => args.filter(Boolean).join(' ');

// Type Definitions
interface Attachment {
  url: string;
  name: string;
  contentType: string;
  size: number;
}

export interface UIMessage {
  id: string;
  content: string;
  role: string;
  attachments?: Attachment[];
}

type VisibilityType = 'public' | 'private' | 'unlisted' | string;

// Utility Functions
const cn = (...inputs: unknown[]) => twMerge(clsx(inputs));

// Button variants using cva
const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'bg-black text-white hover:bg-gray-800',
        destructive: 'border border-black text-black hover:bg-gray-100',
        outline: 'border border-gray-400 bg-white hover:bg-gray-100 hover:text-black',
        secondary: 'bg-gray-200 text-black hover:bg-gray-300',
        ghost: 'text-black hover:bg-gray-100 hover:text-black',
        link: 'text-black underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 rounded-md px-3',
        lg: 'h-11 rounded-md px-8',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  },
);

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props}
    />
  ),
);
Button.displayName = 'Button';

const Textarea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<'textarea'>>(
  ({ className, ...props }, ref) => (
    <textarea
      className={cn(
        'flex min-h-[80px] w-full rounded-md border border-gray-400 bg-white px-3 py-2 text-base ring-offset-white placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 md:text-sm text-black',
        className,
      )}
      ref={ref}
      {...props}
    />
  ),
);
Textarea.displayName = 'Textarea';

const StopIcon = ({ size = 16 }: { size?: number }) => (
  <svg height={size} viewBox="0 0 16 16" width={size} style={{ color: 'currentcolor' }}>
    <path fillRule="evenodd" clipRule="evenodd" d="M3 3H13V13H3V3Z" fill="currentColor" />
  </svg>
);

const ArrowUpIcon = ({ size = 16 }: { size?: number }) => (
  <svg height={size} strokeLinejoin="round" viewBox="0 0 16 16" width={size} style={{ color: 'currentcolor' }}>
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M8.70711 1.39644C8.31659 1.00592 7.68342 1.00592 7.2929 1.39644L2.21968 6.46966L1.68935 6.99999L2.75001 8.06065L3.28034 7.53032L7.25001 3.56065V14.25V15H8.75001V14.25V3.56065L12.7197 7.53032L13.25 8.06065L14.3107 6.99999L13.7803 6.46966L8.70711 1.39644Z"
      fill="currentColor"
    />
  </svg>
);

// ── Suggested Actions ─────────────────────────────────────────────────────────

interface SuggestedActionsProps {
  onSelectAction: (action: string) => void;
}

const PRMS_SUGGESTED_ACTIONS = [
  { title: 'Show all', label: 'active resources', action: 'Show all active resources' },
  { title: 'Which projects', label: 'are overdue?', action: 'Which projects are overdue?' },
  { title: 'List resources', label: 'who know Python', action: 'List resources who know Python' },
  { title: 'Show projects', label: 'for active clients', action: 'Show projects for active clients' },
];

function PureSuggestedActions({ onSelectAction }: SuggestedActionsProps) {
  return (
    <div className="grid pb-2 sm:grid-cols-2 gap-2 w-full">
      <AnimatePresence>
        {PRMS_SUGGESTED_ACTIONS.map((action, index) => (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ delay: 0.05 * index }}
            key={`suggested-action-${index}`}
            className={index > 1 ? 'hidden sm:block' : 'block'}
          >
            <Button
              variant="ghost"
              onClick={() => onSelectAction(action.action)}
              className="text-left border rounded-xl px-4 py-3.5 text-sm flex-1 gap-1 sm:flex-col w-full h-auto justify-start items-start border-gray-300 bg-white hover:bg-gray-100 text-black hover:text-gray-900"
            >
              <span className="font-medium">{action.title}</span>
              <span className="text-gray-500">{action.label}</span>
            </Button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

export const SuggestedActions = memo(PureSuggestedActions);

// ── Attachment preview ────────────────────────────────────────────────────────

const PreviewAttachment = ({
  attachment,
  isUploading = false,
}: {
  attachment: Attachment;
  isUploading?: boolean;
}) => {
  const { name, url, contentType } = attachment;
  return (
    <div className="flex flex-col gap-1">
      <div className="w-20 h-16 aspect-video bg-gray-200 rounded-md relative flex flex-col items-center justify-center overflow-hidden border border-gray-300">
        {contentType?.startsWith('image/') && url ? (
          <img key={url} src={url} alt={name ?? 'attachment'} className="rounded-md size-full object-cover grayscale" />
        ) : (
          <div className="flex items-center justify-center text-xs text-gray-600 text-center p-1">
            {name?.split('.').pop()?.toUpperCase() || 'File'}
          </div>
        )}
        {isUploading && (
          <div className="animate-spin absolute text-gray-500">
            <LoaderIcon className="size-5" />
          </div>
        )}
      </div>
      <div className="text-xs text-gray-600 max-w-20 truncate">{name}</div>
    </div>
  );
};

function PureStopButton({ onStop }: { onStop: () => void }) {
  return (
    <Button
      className="rounded-full p-1.5 h-fit border border-black text-white"
      onClick={(e) => { e.preventDefault(); onStop(); }}
      aria-label="Stop generating"
    >
      <StopIcon size={14} />
    </Button>
  );
}
const StopButton = memo(PureStopButton, (prev, next) => prev.onStop === next.onStop);

function PureSendButton({
  submitForm, input, uploadQueue, attachments, canSend, isGenerating,
}: {
  submitForm: () => void;
  input: string;
  uploadQueue: string[];
  attachments: Attachment[];
  canSend: boolean;
  isGenerating: boolean;
}) {
  const isDisabled =
    uploadQueue.length > 0 || !canSend || isGenerating ||
    (input.trim().length === 0 && attachments.length === 0);

  return (
    <Button
      className="rounded-full p-1.5 h-fit"
      onClick={(e) => { e.preventDefault(); if (!isDisabled) submitForm(); }}
      disabled={isDisabled}
      aria-label="Send message"
    >
      <ArrowUpIcon size={14} />
    </Button>
  );
}
const SendButton = memo(PureSendButton, (prev, next) => {
  if (prev.input !== next.input) return false;
  if (prev.uploadQueue.length !== next.uploadQueue.length) return false;
  if (prev.attachments.length !== next.attachments.length) return false;
  if (prev.attachments.length > 0 && !equal(prev.attachments, next.attachments)) return false;
  if (prev.canSend !== next.canSend) return false;
  if (prev.isGenerating !== next.isGenerating) return false;
  return true;
});

// ── Main Component ────────────────────────────────────────────────────────────

export interface MultimodalInputProps {
  chatId: string;
  messages: UIMessage[];
  attachments: Attachment[];
  setAttachments: Dispatch<SetStateAction<Attachment[]>>;
  onSendMessage: (params: { input: string; attachments: Attachment[] }) => void;
  onStopGenerating: () => void;
  isGenerating: boolean;
  canSend: boolean;
  className?: string;
  selectedVisibilityType?: VisibilityType;
  /** When true, hides suggested action cards even if no messages exist */
  hideSuggestions?: boolean;
}

export function PureMultimodalInput({
  chatId: _chatId, // reserved — not used internally but kept in API for callers
  messages,
  attachments,
  setAttachments,
  onSendMessage,
  onStopGenerating,
  isGenerating,
  canSend,
  className,
  selectedVisibilityType: _vis, // reserved — not used internally
  hideSuggestions = false,
}: MultimodalInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [input, setInput] = useState('');
  const [uploadQueue, setUploadQueue] = useState<string[]>([]);

  const adjustHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${textarea.scrollHeight + 2}px`;
    }
  };

  const resetHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.rows = 1;
      adjustHeight();
    }
  }, []);

  useEffect(() => {
    if (textareaRef.current) adjustHeight();
  }, [input]);

  const handleInput = (event: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(event.target.value);
  };

  const uploadFile = async (file: File): Promise<Attachment | undefined> => {
    return new Promise((resolve) => {
      setTimeout(() => {
        try {
          const mockUrl = URL.createObjectURL(file);
          resolve({ url: mockUrl, name: file.name, contentType: file.type || 'application/octet-stream', size: file.size });
        } catch {
          resolve(undefined);
        } finally {
          setUploadQueue((q) => q.filter((n) => n !== file.name));
        }
      }, 700);
    });
  };

  const handleFileChange = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    setUploadQueue((q) => [...q, ...files.map((f) => f.name)]);
    if (fileInputRef.current) fileInputRef.current.value = '';

    const MAX = 25 * 1024 * 1024;
    const valid = files.filter((f) => f.size <= MAX);
    const invalid = files.filter((f) => f.size > MAX);
    if (invalid.length) setUploadQueue((q) => q.filter((n) => !invalid.some((f) => f.name === n)));

    const uploaded = (await Promise.all(valid.map(uploadFile))).filter((a): a is Attachment => !!a);
    setAttachments((curr) => [...curr, ...uploaded]);
  }, [setAttachments]);

  const handleRemoveAttachment = useCallback((toRemove: Attachment) => {
    if (toRemove.url.startsWith('blob:')) URL.revokeObjectURL(toRemove.url);
    setAttachments((curr) => curr.filter((a) => a.url !== toRemove.url || a.name !== toRemove.name));
    textareaRef.current?.focus();
  }, [setAttachments]);

  const submitForm = useCallback(() => {
    if (!input.trim() && !attachments.length) return;
    onSendMessage({ input, attachments });
    setInput('');
    setAttachments([]);
    attachments.forEach((a) => { if (a.url.startsWith('blob:')) URL.revokeObjectURL(a.url); });
    resetHeight();
    textareaRef.current?.focus();
  }, [input, attachments, onSendMessage, setAttachments, resetHeight]);

  const showSuggested = !hideSuggestions && messages.length === 0 && !attachments.length && !uploadQueue.length;

  return (
    <div className={cn('relative w-full flex flex-col gap-4', className)}>
      <AnimatePresence>
        {showSuggested && (
          <motion.div
            key="suggested-actions"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            transition={{ duration: 0.2 }}
          >
            <SuggestedActions
              onSelectAction={(action) => {
                setInput(action);
                requestAnimationFrame(() => { adjustHeight(); textareaRef.current?.focus(); });
              }}
            />
          </motion.div>
        )}
      </AnimatePresence>

      <input
        type="file"
        className="fixed -top-4 -left-4 size-0.5 opacity-0 pointer-events-none"
        ref={fileInputRef}
        multiple
        onChange={handleFileChange}
        tabIndex={-1}
        disabled={isGenerating || uploadQueue.length > 0}
        accept="image/*,video/*,audio/*,.pdf"
      />

      {(attachments.length > 0 || uploadQueue.length > 0) && (
        <div className="flex pt-[10px] flex-row gap-3 overflow-x-auto items-end pb-2 pl-1">
          {attachments.map((a) => (
            <div key={a.url || a.name} className="relative group">
              <PreviewAttachment attachment={a} />
              <Button
                variant="destructive"
                size="icon"
                className="absolute top-[-8px] right-[-8px] h-5 w-5 rounded-full p-0 flex items-center justify-center z-20 opacity-0 group-hover:opacity-100 transition-opacity"
                onClick={() => handleRemoveAttachment(a)}
              >
                <XIcon className="size-3" />
              </Button>
            </div>
          ))}
          {uploadQueue.map((filename, i) => (
            <PreviewAttachment
              key={`upload-${filename}-${i}`}
              attachment={{ url: '', name: filename, contentType: '', size: 0 }}
              isUploading
            />
          ))}
        </div>
      )}

      <Textarea
        ref={textareaRef}
        placeholder="Ask a question about your data..."
        value={input}
        onChange={handleInput}
        className={cn(
          'min-h-[24px] max-h-[calc(75dvh)] overflow-y-auto resize-none rounded-2xl !text-base pb-10',
          'bg-gray-100 border border-gray-300',
          className,
        )}
        style={{ color: 'black' }}
        rows={1}
        autoFocus
        disabled={!canSend || isGenerating || uploadQueue.length > 0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            if (canSend && !isGenerating && !uploadQueue.length && (input.trim().length > 0 || attachments.length > 0)) {
              submitForm();
            }
          }
        }}
      />

      <div className="absolute bottom-0 left-0 p-2 w-fit flex flex-row justify-start z-10">
        <Button
          className="rounded-md rounded-bl-lg p-[7px] h-fit border border-gray-300 hover:bg-gray-200"
          onClick={(e) => { e.preventDefault(); fileInputRef.current?.click(); }}
          disabled={isGenerating || uploadQueue.length > 0}
          variant="ghost"
          aria-label="Attach files"
        >
          {/* Paperclip */}
          <svg height={14} strokeLinejoin="round" viewBox="0 0 16 16" width={14} style={{ color: 'currentcolor' }} className="-rotate-45">
            <path fillRule="evenodd" clipRule="evenodd" d="M10.8591 1.70735C10.3257 1.70735 9.81417 1.91925 9.437 2.29643L3.19455 8.53886C2.56246 9.17095 2.20735 10.0282 2.20735 10.9222C2.20735 11.8161 2.56246 12.6734 3.19455 13.3055C3.82665 13.9376 4.68395 14.2927 5.57786 14.2927C6.47178 14.2927 7.32908 13.9376 7.96117 13.3055L14.2036 7.06304L14.7038 6.56287L15.7041 7.56321L15.204 8.06337L8.96151 14.3058C8.06411 15.2032 6.84698 15.7074 5.57786 15.7074C4.30875 15.7074 3.09162 15.2032 2.19422 14.3058C1.29682 13.4084 0.792664 12.1913 0.792664 10.9222C0.792664 9.65305 1.29682 8.43592 2.19422 7.53852L8.43666 1.29609C9.07914 0.653606 9.95054 0.292664 10.8591 0.292664C11.7678 0.292664 12.6392 0.653606 13.2816 1.29609C13.9241 1.93857 14.2851 2.80997 14.2851 3.71857C14.2851 4.62718 13.9241 5.49858 13.2816 6.14106L7.0324 12.3835C6.64459 12.7712 6.11905 12.9888 5.57107 12.9888C5.02297 12.9888 4.49731 12.7711 4.10974 12.3835C3.72217 11.9959 3.50444 11.4703 3.50444 10.9222C3.50444 10.3741 3.72217 9.8484 4.10974 9.46084L9.877 3.70039L10.3775 3.20051L11.3772 4.20144L10.8767 4.70131L5.11008 10.4612C4.98779 10.5835 4.91913 10.7493 4.91913 10.9222C4.91913 11.0951 4.98782 11.2609 5.11008 11.3832C5.23234 11.5054 5.39817 11.5741 5.57107 11.5741C5.74398 11.5741 5.9098 11.5054 6.03206 11.3832L12.2813 5.14072C12.6586 4.7633 12.8704 4.25185 12.8704 3.71857C12.8704 3.18516 12.6585 2.6736 12.2813 2.29643C11.9041 1.91925 11.3926 1.70735 10.8591 1.70735Z" fill="currentColor" />
          </svg>
        </Button>
      </div>

      <div className="absolute bottom-0 right-0 p-2 w-fit flex flex-row justify-end z-10">
        {isGenerating ? (
          <StopButton onStop={onStopGenerating} />
        ) : (
          <SendButton
            submitForm={submitForm}
            input={input}
            uploadQueue={uploadQueue}
            attachments={attachments}
            canSend={canSend}
            isGenerating={isGenerating}
          />
        )}
      </div>
    </div>
  );
}
