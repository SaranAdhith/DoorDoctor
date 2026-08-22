import { Navigate, Route, Routes } from 'react-router-dom'

import { ROLE_HOME, useAuth } from './auth/AuthContext'
import { ProtectedRoute } from './auth/ProtectedRoute'
import { AppShell } from './components/layout/AppShell'
import { ForgotPassword } from './pages/ForgotPassword'
import { Login } from './pages/Login'
import { ResetPassword } from './pages/ResetPassword'
import { NurseVisitDetail } from './pages/nurse/NurseVisitDetail'
import { NurseVisits } from './pages/nurse/NurseVisits'
import { AdminAlerts } from './pages/admin/AdminAlerts'
import { AdminNurses } from './pages/admin/AdminNurses'
import { AdminDashboard } from './pages/admin/AdminDashboard'
import { AdminPatients } from './pages/admin/AdminPatients'
import { AdminVisits } from './pages/admin/AdminVisits'
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
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />

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
        path="/nurse"
        element={
          <ProtectedRoute allow={['nurse']}>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/nurse/visits" replace />} />
        <Route path="visits" element={<NurseVisits />} />
        <Route path="visits/:visitId" element={<NurseVisitDetail />} />
      </Route>

      <Route
        path="/admin"
        element={
          <ProtectedRoute allow={['admin']}>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/admin/dashboard" replace />} />
        <Route path="dashboard" element={<AdminDashboard />} />
        <Route path="patients" element={<AdminPatients />} />
        <Route path="patients/:patientId" element={<PatientProfile />} />
        <Route path="nurses" element={<AdminNurses />} />
        <Route path="visits" element={<AdminVisits />} />
        <Route path="alerts" element={<AdminAlerts />} />
      </Route>

      <Route path="/" element={<RootRedirect />} />
      <Route path="*" element={<RootRedirect />} />
    </Routes>
  )
}
