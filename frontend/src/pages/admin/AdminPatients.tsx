import { Link } from 'react-router-dom'

import { patientsApi } from '../../api/patients'
import { Card, EmptyState } from '../../components/common/Card'
import { ErrorBanner } from '../../components/common/ErrorBanner'
import { LoadingScreen } from '../../components/common/Loading'
import { useAsync } from '../../hooks/useAsync'
import { formatDate } from '../../lib/format'
import type { Patient } from '../../types'

export function AdminPatients() {
  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])

  if (patients.loading) return <LoadingScreen label="Loading patients" />
  if (patients.error) return <ErrorBanner message={patients.error} onRetry={() => void patients.reload()} />

  const rows = patients.data ?? []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy-800">Patients</h1>
        <p className="mt-1 text-sm text-slate-500">Everyone enrolled in the DoorDoctor demo programme.</p>
      </div>

      <Card>
        {rows.length === 0 ? (
          <EmptyState title="No patients enrolled" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="pb-2 pr-4 font-semibold">Name</th>
                  <th className="pb-2 pr-4 font-semibold">Age</th>
                  <th className="pb-2 pr-4 font-semibold">Address</th>
                  <th className="pb-2 pr-4 font-semibold">Enrolled</th>
                  <th className="pb-2 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((patient) => (
                  <tr key={patient.id}>
                    <td className="py-2.5 pr-4 font-medium text-navy-800">
                      <Link to={`/admin/patients/${patient.id}`} className="hover:underline">
                        {patient.name}
                      </Link>
                    </td>
                    <td className="py-2.5 pr-4 tabular-nums text-slate-700">{patient.age}</td>
                    <td className="py-2.5 pr-4 text-slate-600">{patient.address}</td>
                    <td className="py-2.5 pr-4 text-slate-600">{formatDate(patient.created_at)}</td>
                    <td className="py-2.5 capitalize text-slate-700">{patient.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}
