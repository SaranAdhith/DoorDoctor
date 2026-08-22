import { useState } from 'react'
import { Download, FileText } from 'lucide-react'

import { patientsApi } from '../../api/patients'
import { openReportPdf, reportsApi } from '../../api/summary'
import { useAsync } from '../../hooks/useAsync'
import { formatDate } from '../../lib/format'
import type { Patient, Report, SummaryHighlight } from '../../types'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorState,
  LoadingScreen,
  Select,
  useToast,
  type BadgeTone,
} from '../../components/ui'

const TONES: Record<SummaryHighlight['tone'], BadgeTone> = {
  good: 'good',
  watch: 'watch',
  attention: 'attention',
}

function ReportCard({ report, onOpen }: { report: Report; onOpen: (report: Report) => void }) {
  return (
    <Card
      title={report.title}
      description={`${formatDate(report.period_start)} — ${formatDate(report.period_end)}`}
      action={
        <Button
          variant="ghost"
          size="sm"
          icon={<Download className="h-4 w-4" aria-hidden="true" />}
          onClick={() => onOpen(report)}
        >
          Open PDF
        </Button>
      }
    >
      <p className="text-body font-semibold leading-snug text-text-primary">{report.headline}</p>

      {report.highlights.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-2">
          {report.highlights.map((highlight) => (
            <li key={highlight.text}>
              <Badge tone={TONES[highlight.tone]}>{highlight.text}</Badge>
            </li>
          ))}
        </ul>
      )}

      <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-small text-text-secondary">
        <div className="flex gap-1.5">
          <dt>Health checks</dt>
          <dd className="tnum font-semibold text-text-primary">{report.reading_count}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt>Nurse visits</dt>
          <dd className="tnum font-semibold text-text-primary">{report.visit_count}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt>Doses recorded</dt>
          <dd className="tnum font-semibold text-text-primary">{report.dose_count}</dd>
        </div>
      </dl>

      <p className="mt-3 text-caption text-text-muted">
        Prepared {formatDate(report.generated_at)}
      </p>
    </Card>
  )
}

export function FamilyReports() {
  const { notify } = useToast()
  const [selectedPatientId, setSelectedPatientId] = useState<number | null>(null)
  const [generating, setGenerating] = useState(false)

  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])
  const patientId = selectedPatientId ?? patients.data?.[0]?.id ?? null

  const reports = useAsync(
    () => (patientId ? reportsApi.list(patientId) : Promise.resolve([])),
    [patientId],
  )

  async function generate() {
    if (!patientId) return
    setGenerating(true)
    try {
      await reportsApi.generate(patientId)
      await reports.reload({ quiet: true })
      notify('Report ready', 'success')
    } catch {
      notify('Could not generate the report. Please try again.', 'error')
    } finally {
      setGenerating(false)
    }
  }

  async function open(report: Report) {
    try {
      await openReportPdf(report.id)
    } catch {
      notify('Could not open the PDF. Please try again.', 'error')
    }
  }

  if (patients.loading) return <LoadingScreen label="Loading reports" />
  if (patients.error) {
    return <ErrorState message={patients.error} onRetry={() => void patients.reload()} />
  }
  if (!patientId) {
    return (
      <EmptyState
        title="No patient linked to this account"
        description="Ask DoorDoctor to link a patient."
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-h1 font-bold text-text-primary">Care reports</h1>
          <p className="mt-1 text-small text-text-secondary">
            A written summary you can keep, share with a doctor, or read on a slow connection.
            DoorDoctor prepares one every Sunday evening and one at the start of each month.
          </p>
        </div>

        <div className="flex shrink-0 items-end gap-3">
          {(patients.data?.length ?? 0) > 1 && (
            <Select
              label="Select patient"
              hideLabel
              className="w-48"
              value={patientId}
              onChange={(event) => setSelectedPatientId(Number(event.target.value))}
            >
              {patients.data?.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </Select>
          )}
          <Button
            onClick={() => void generate()}
            loading={generating}
            icon={<FileText className="h-4 w-4" aria-hidden="true" />}
          >
            Generate one now
          </Button>
        </div>
      </div>

      {reports.error ? (
        <ErrorState message={reports.error} onRetry={() => void reports.reload()} />
      ) : reports.loading && !reports.data ? (
        <LoadingScreen label="Loading reports" />
      ) : (reports.data?.length ?? 0) === 0 ? (
        <EmptyState
          title="No reports yet"
          description="Your first weekly report is prepared on Sunday evening. You can also generate one right now."
        />
      ) : (
        <div className="space-y-4">
          {reports.data?.map((report) => (
            <ReportCard key={report.id} report={report} onOpen={(r) => void open(r)} />
          ))}
        </div>
      )}
    </div>
  )
}
