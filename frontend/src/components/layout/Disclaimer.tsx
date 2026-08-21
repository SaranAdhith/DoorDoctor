import { cn } from '../../lib/cn'

/**
 * The safety disclaimer. Required on every clinical surface — alerts describe
 * configured monitoring thresholds, never a diagnosis.
 */
export function Disclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <p className={cn('text-text-muted', compact ? 'text-caption' : 'text-caption leading-relaxed')}>
      DoorDoctor is a healthcare monitoring and coordination service. Alerts indicate readings outside
      the monitoring thresholds configured for a patient, and are not medical diagnoses. Thresholds and
      escalation procedures are defined and reviewed by qualified clinical professionals.
    </p>
  )
}

/**
 * DoorDoctor is explicitly not an emergency service. This block is permanent on
 * every clinical screen so that is never ambiguous in the moment it matters.
 */
export function EmergencyNotice({ className }: { className?: string }) {
  return (
    <p
      className={cn(
        'rounded-xl border border-status-critical-border bg-status-critical-bg px-3.5 py-2.5',
        'text-small font-medium text-status-critical',
        className,
      )}
    >
      In an emergency, call{' '}
      <a href="tel:108" className="font-bold underline">
        108
      </a>{' '}
      immediately. DoorDoctor is a monitoring service, not an emergency service.
    </p>
  )
}
