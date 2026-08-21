import { cn } from '../../lib/cn'

interface Props {
  /**
   * `header` is the mark + wordmark used in the sidebar and top bar.
   * `mark` is the mark alone, for a collapsed sidebar or a narrow header.
   * `lockup` is the full stacked logo used on the auth and public pages.
   */
  variant?: 'header' | 'mark' | 'lockup'
  className?: string
  /** The "Elderly Healthcare" strapline. Dropped where width is tight. */
  showStrapline?: boolean
}

export function Logo({ variant = 'header', className, showStrapline = true }: Props) {
  if (variant === 'lockup') {
    return (
      <img
        src="/doordoctor-logo.png"
        alt="DoorDoctor"
        className={cn('h-auto w-48', className)}
        width={720}
        height={461}
      />
    )
  }

  if (variant === 'mark') {
    return (
      <img
        src="/doordoctor-mark.png"
        alt="DoorDoctor"
        className={cn('h-8 w-auto', className)}
        width={256}
        height={150}
      />
    )
  }

  return (
    <span className={cn('flex min-w-0 items-center gap-2.5', className)}>
      <img
        src="/doordoctor-mark.png"
        alt=""
        aria-hidden="true"
        className="h-8 w-auto"
        width={256}
        height={150}
      />
      <span className="min-w-0 leading-tight">
        <span className="block whitespace-nowrap text-body font-extrabold tracking-tight text-text-primary">
          DOOR<span className="text-brand-500">DOCTOR</span>
        </span>
        {/* The strapline is the first thing to go when width is tight. */}
        {showStrapline && (
          <span className="block whitespace-nowrap text-caption font-medium uppercase tracking-[0.14em] text-text-muted">
            Elderly Healthcare
          </span>
        )}
      </span>
    </span>
  )
}
