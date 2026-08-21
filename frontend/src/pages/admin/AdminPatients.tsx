import { Link } from 'react-router-dom'

import { patientsApi } from '../../api/patients'
import { useAsync } from '../../hooks/useAsync'
import { formatDate } from '../../lib/format'
import type { Patient } from '../../types'
import { Card, EmptyState, ErrorState, LoadingScreen } from '../../components/ui'

export function AdminPatients() {
  const patients = useAsync<Patient[]>(() => patientsApi.list(), [])

  if (patients.loading) return <LoadingScreen label="Loading patients" />
  if (patients.error) return <ErrorState message={patients.error} onRetry={() => void patients.reload()} />

  const rows = patients.data ?? []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-text-primary">Patients</h1>
        <p className="mt-1 text-small text-text-secondary">Everyone enrolled in the DoorDoctor demo programme.</p>
      </div>

      <Card>
        {rows.length === 0 ? (
          <EmptyState title="No patients enrolled" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-small">
              <thead>
                <tr className="text-left text-caption uppercase tracking-wide text-text-secondary">
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
                    <td className="py-2.5 pr-4 font-medium text-text-primary">
                      <Link to={`/admin/patients/${patient.id}`} className="hover:underline">
                        {patient.name}
                      </Link>
                    </td>
                    <td className="py-2.5 pr-4 tnum text-text-primary">{patient.age}</td>
                    <td className="py-2.5 pr-4 text-text-secondary">{patient.address}</td>
                    <td className="py-2.5 pr-4 text-text-secondary">{formatDate(patient.created_at)}</td>
                    <td className="py-2.5 capitalize text-text-primary">{patient.status}</td>
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
