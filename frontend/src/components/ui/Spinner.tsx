import { cn } from '../../lib/cn'

export function Spinner({ className = 'h-5 w-5' }: { className?: string }) {
  return (
    <svg
      className={cn('animate-spin', className)}
      viewBox="0 0 24 24"
      role="presentation"
      aria-hidden="true"
    >
      <circle
        className="opacity-20"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
        fill="none"
      />
      <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 0 1 8-8v4a4 4 0 0 0-4 4H4z" />
    </svg>
  )
}

export function LoadingScreen({ label = 'Loading' }: { label?: string }) {
  return (
    <div
      className="flex min-h-[60vh] flex-col items-center justify-center gap-3 text-text-secondary"
      role="status"
      aria-live="polite"
    >
      <Spinner className="h-8 w-8 text-brand-500" />
      <p className="text-small font-medium">{label}…</p>
    </div>
  )
}
