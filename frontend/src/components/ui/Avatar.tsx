import { cn } from '../../lib/cn'

const SIZES = {
  sm: 'h-8 w-8 text-caption',
  md: 'h-10 w-10 text-small',
  lg: 'h-14 w-14 text-body',
  xl: 'h-20 w-20 text-h2',
} as const

export interface AvatarProps {
  name: string
  src?: string | null
  size?: keyof typeof SIZES
  className?: string
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

export function Avatar({ name, src, size = 'md', className }: AvatarProps) {
  const classes = cn(
    'inline-flex shrink-0 items-center justify-center overflow-hidden rounded-full',
    SIZES[size],
    className,
  )

  if (src) {
    return <img src={src} alt="" aria-hidden="true" className={cn(classes, 'object-cover')} />
  }

  // The name is already rendered next to every avatar we place, so the
  // initials are decorative and hidden rather than read out twice.
  return (
    <span className={cn(classes, 'bg-navy-100 font-semibold text-navy-700')} aria-hidden="true">
      {initials(name)}
    </span>
  )
}
