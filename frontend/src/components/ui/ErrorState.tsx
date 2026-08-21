import { AlertTriangle } from 'lucide-react'

import { cn } from '../../lib/cn'
import { Button } from './Button'

export interface ErrorStateProps {
  message: string
  onRetry?: () => void
  className?: string
}

/**
 * The one way this product reports a failed load. `role="alert"` so it is
 * announced the moment it replaces a spinner.
 */
export function ErrorState({ message, onRetry, className }: ErrorStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-3 rounded-2xl border border-critical-200 bg-status-critical-bg px-4 py-3.5',
        'text-small text-status-critical sm:flex-row sm:items-center sm:justify-between',
        className,
      )}
      role="alert"
    >
      <span className="flex items-start gap-2.5 font-medium">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
        {message}
      </span>
      {onRetry && (
        <Button variant="ghost" size="sm" onClick={onRetry} className="self-start sm:self-auto">
          Try again
        </Button>
      )}
    </div>
  )
}
