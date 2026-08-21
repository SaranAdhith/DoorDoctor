import { Navigate, Route, Routes } from 'react-router-dom'

import { ROLE_HOME, useAuth } from './auth/AuthContext'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { AppShell } from './components/layout/AppShell'
import { Login } from './pages/Login'
import { CaregiverVisitDetail } from './pages/caregiver/CaregiverVisitDetail'
import { CaregiverVisits } from './pages/caregiver/CaregiverVisits'
import { CoordinatorAlerts } from './pages/coordinator/CoordinatorAlerts'
import { CoordinatorCaregivers } from './pages/coordinator/CoordinatorCaregivers'
import { CoordinatorDashboard } from './pages/coordinator/CoordinatorDashboard'
import { CoordinatorPatients } from './pages/coordinator/CoordinatorPatients'
import { CoordinatorVisits } from './pages/coordinator/CoordinatorVisits'
import { FamilyAlerts } from './pages/family/FamilyAlerts'
import { FamilyDashboard } from './pages/family/FamilyDashboard'
import { FamilyMedications } from './pages/family/FamilyMedications'
import { PatientProfile } from './pages/family/PatientProfile'

function RootRedirect() {
  const { user, initialising } = useAuth()
  if (initialising) return null
  return <Navigate to={user ? ROLE_HOME[user.role] : '/login'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route
        path="/family"
        element={
          <ProtectedRoute allow={['family']}>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/family/dashboard" replace />} />
        <Route path="dashboard" element={<FamilyDashboard />} />
        <Route path="patient/:patientId" element={<PatientProfile />} />
        <Route path="medications" element={<FamilyMedications />} />
        <Route path="alerts" element={<FamilyAlerts />} />
      </Route>

      <Route
        path="/caregiver"
        element={
          <ProtectedRoute allow={['caregiver']}>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/caregiver/visits" replace />} />
        <Route path="visits" element={<CaregiverVisits />} />
        <Route path="visits/:visitId" element={<CaregiverVisitDetail />} />
      </Route>

      <Route
        path="/coordinator"
        element={
          <ProtectedRoute allow={['coordinator']}>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/coordinator/dashboard" replace />} />
        <Route path="dashboard" element={<CoordinatorDashboard />} />
        <Route path="patients" element={<CoordinatorPatients />} />
        <Route path="patients/:patientId" element={<PatientProfile />} />
        <Route path="caregivers" element={<CoordinatorCaregivers />} />
        <Route path="visits" element={<CoordinatorVisits />} />
        <Route path="alerts" element={<CoordinatorAlerts />} />
      </Route>

      <Route path="/" element={<RootRedirect />} />
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  )
}
