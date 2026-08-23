import { MapPin, MapPinOff, Navigation } from 'lucide-react'

import { Badge, Tooltip } from '../ui'
import type { LocationStatus } from '../../types'

/**
 * What the platform is willing to claim about where a check-in happened (§4.11).
 *
 * Three states and three tones, and `unavailable` is deliberately **neutral**
 * rather than a warning colour. "We do not know where the nurse was" is a true
 * statement, not a fault — colouring it red would train a family to read a
 * missing GPS fix as a missing nurse.
 *
 * The measured distance is shown beside the label whenever there is one, so
 * `verified` is arithmetic the reader can check rather than a badge the
 * platform awarded itself.
 */
export interface LocationBadgeProps {
  status: LocationStatus
  distanceM?: number | null
  detail?: string | null
  className?: string
}

const LABELS: Record<LocationStatus, string> = {
  verified: 'Location verified',
  out_of_range: 'Away from home',
  unavailable: 'Location not recorded',
}

const TONES = {
  verified: 'good',
  out_of_range: 'watch',
  unavailable: 'neutral',
} as const

const ICONS = {
  verified: MapPin,
  out_of_range: Navigation,
  unavailable: MapPinOff,
}

export function formatDistance(metres: number): string {
  return metres >= 1000 ? `${(metres / 1000).toFixed(1)} km` : `${Math.round(metres)} m`
}

export function LocationBadge({ status, distanceM, detail, className }: LocationBadgeProps) {
  const Icon = ICONS[status]
  const label =
    status !== 'unavailable' && distanceM != null
      ? `${LABELS[status]} · ${formatDistance(distanceM)}`
      : LABELS[status]

  const badge = (
    <Badge tone={TONES[status]} className={className}>
      <Icon aria-hidden className="mr-1 inline h-3.5 w-3.5" />
      {label}
    </Badge>
  )

  return detail ? <Tooltip content={detail}>{badge}</Tooltip> : badge
}
