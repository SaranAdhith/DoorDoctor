interface Props {
  /** `lockup` is the stacked mark + wordmark used on the login screen. */
  variant?: 'header' | 'lockup'
  className?: string
}

export function Logo({ variant = 'header', className = '' }: Props) {
  if (variant === 'lockup') {
    return (
      <img
        src="/doordoctor-logo.png"
        alt="DoorDoctor"
        className={`h-auto w-48 ${className}`}
        width={720}
        height={461}
      />
    )
  }

  return (
    <span className={`flex items-center gap-2.5 ${className}`}>
      <img
        src="/doordoctor-mark.png"
        alt=""
        aria-hidden="true"
        className="h-8 w-auto"
        width={256}
        height={150}
      />
      <span className="leading-tight">
        <span className="block text-base font-extrabold tracking-tight text-navy-800">
          DOOR<span className="text-brand-500">DOCTOR</span>
        </span>
        <span className="hidden text-[11px] font-medium uppercase tracking-[0.14em] text-slate-500 sm:block">
          Elderly Healthcare
        </span>
      </span>
    </span>
  )
}
