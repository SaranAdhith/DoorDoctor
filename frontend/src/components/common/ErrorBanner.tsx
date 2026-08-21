interface Props {
  message: string
  onRetry?: () => void
}

export function ErrorBanner({ message, onRetry }: Props) {
  return (
    <div
      className="flex flex-col gap-3 rounded-2xl border border-critical-200 bg-critical-50 px-4 py-3.5 text-sm text-critical-700 sm:flex-row sm:items-center sm:justify-between"
      role="alert"
    >
      <span className="font-medium">{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-ghost self-start py-1.5 text-xs sm:self-auto">
          Try again
        </button>
      )}
    </div>
  )
}
