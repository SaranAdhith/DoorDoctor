import type { PlainSummary, Report, ReportKind, SummaryWindow } from '../types'
import { api, requestBlob } from './client'

export const summaryApi = {
  plain: (patientId: number, window: SummaryWindow) =>
    api.get<PlainSummary>(`/patients/${patientId}/plain-summary?window=${window}`),
}

export const reportsApi = {
  list: (patientId: number) => api.get<Report[]>(`/patients/${patientId}/reports`),
  generate: (patientId: number, kind: ReportKind = 'on_demand') =>
    api.post<Report>(`/patients/${patientId}/reports/generate`, { kind }),
  pdf: (reportId: number) => requestBlob(`/reports/${reportId}/pdf`),
}

/**
 * Opens a report PDF in a new tab.
 *
 * Same shape as `openInvoicePdf`, and for the same two reasons: the endpoint is
 * authenticated so a plain `<a href>` would 401, and the blob URL is revoked on
 * a delay because Safari has not finished reading it when `open()` returns.
 */
export async function openReportPdf(reportId: number): Promise<void> {
  const blob = await reportsApi.pdf(reportId)
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank', 'noopener')
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
}
