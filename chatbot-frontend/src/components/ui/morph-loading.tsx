import { cn } from '@/lib/utils'

interface MorphLoadingProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const containerSizes = {
  sm: 'w-16 h-16',
  md: 'w-24 h-24',
  lg: 'w-32 h-32',
}

export function MorphLoading({ size = 'md', className }: MorphLoadingProps) {
  return (
    <div className={cn('relative', containerSizes[size], className)}>
      <div className="absolute inset-0 flex items-center justify-center">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className="absolute w-4 h-4 bg-black dark:bg-white"
            style={{
              animation: `morph-${i} 2s infinite ease-in-out`,
              animationDelay: `${i * 0.2}s`,
            }}
          />
        ))}
      </div>
    </div>
  )
}
