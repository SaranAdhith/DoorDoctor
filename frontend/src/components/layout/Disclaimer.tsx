export function Disclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <p className={`text-slate-500 ${compact ? 'text-[11px]' : 'text-xs leading-relaxed'}`}>
      DoorDoctor is a healthcare monitoring and coordination prototype. Alerts indicate configured
      monitoring thresholds and are not medical diagnoses. In a real deployment, thresholds and
      escalation procedures must be defined and validated by qualified clinical professionals.
    </p>
  )
}
