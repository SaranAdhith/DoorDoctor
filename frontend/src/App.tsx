import { Navigate, Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from './auth/ProtectedRoute'
import { AppShell } from './components/layout/AppShell'
import { PublicLayout } from './components/public'
import { ForgotPassword } from './pages/ForgotPassword'
import { Login } from './pages/Login'
import { ResetPassword } from './pages/ResetPassword'
import { About } from './pages/public/About'
import { Contact } from './pages/public/Contact'
import { Faq } from './pages/public/Faq'
import { Home } from './pages/public/Home'
import { HowItWorks } from './pages/public/HowItWorks'
import { NotFound } from './pages/public/NotFound'
import { Nri } from './pages/public/Nri'
import { Pricing } from './pages/public/Pricing'
import { PricingCorporate } from './pages/public/PricingCorporate'
import { PricingInstitutions } from './pages/public/PricingInstitutions'
import { Privacy } from './pages/public/Privacy'
import { Terms } from './pages/public/Terms'
import { TrustAndSafety } from './pages/public/TrustAndSafety'
import { WhatIsDoorDoctor } from './pages/public/WhatIsDoorDoctor'
import { WhoItsFor } from './pages/public/WhoItsFor'
import { NurseMyDay } from './pages/nurse/NurseMyDay'
import { NurseRoster } from './pages/nurse/NurseRoster'
import { NurseVisitDetail } from './pages/nurse/NurseVisitDetail'
import { NurseVisits } from './pages/nurse/NurseVisits'
import { AdminAlerts } from './pages/admin/AdminAlerts'
import { AdminOutcomes } from './pages/admin/AdminOutcomes'
import { AdminPrivacy } from './pages/admin/AdminPrivacy'
import { AdminVisitBoard } from './pages/admin/AdminVisitBoard'
import { AdminZones } from './pages/admin/AdminZones'
import { AdminCare } from './pages/admin/AdminCare'
import { AdminEscalations } from './pages/admin/AdminEscalations'
import { AdminLabs } from './pages/admin/AdminLabs'
import { AdminAssistant } from './pages/admin/AdminAssistant'
import { AdminLeads } from './pages/admin/AdminLeads'
import { AdminRevenue } from './pages/admin/AdminRevenue'
import { AdminSubscriptions } from './pages/admin/AdminSubscriptions'
import { AdminNurses } from './pages/admin/AdminNurses'
import { AdminDashboard } from './pages/admin/AdminDashboard'
import { AdminPatients } from './pages/admin/AdminPatients'
import { AdminVisits } from './pages/admin/AdminVisits'
import { FamilyAlerts } from './pages/family/FamilyAlerts'
import { FamilyCareCircle } from './pages/family/FamilyCareCircle'
import { FamilyNotifications } from './pages/family/FamilyNotifications'
import { FamilyNurseProfile } from './pages/family/FamilyNurseProfile'
import { FamilyPrivacy } from './pages/family/FamilyPrivacy'
import { FamilyCareTeam } from './pages/family/FamilyCareTeam'
import { FamilyConsults } from './pages/family/FamilyConsults'
import { FamilyLabs } from './pages/family/FamilyLabs'
import { FamilyAssistant } from './pages/family/FamilyAssistant'
import { FamilyDashboard } from './pages/family/FamilyDashboard'
import { FamilyMedications } from './pages/family/FamilyMedications'
import { FamilyReports } from './pages/family/FamilyReports'
import { MyPlan } from './pages/family/MyPlan'
import { PatientProfile } from './pages/family/PatientProfile'

/**
 * Three shells, one router.
 *
 * `PublicLayout` — the marketing site, open to everyone.
 * `AuthLayout` (inside the three auth pages) — sign in, forgot, reset.
 * `AppShell` behind `ProtectedRoute` — the product.
 *
 * **`/` renders the public home for everyone, signed in or not.** Phase 8
 * replaced the old `RootRedirect`, and this was decided explicitly rather than
 * allowed to happen: a signed-in family member who follows a link to `/pricing`
 * or `/about` must be able to read it, and a redirect at `/` but not at
 * `/pricing` is an inconsistency someone would have to remember. The public
 * header offers "Go to dashboard" when a session exists, which is the useful
 * half of the old redirect without the trap.
 *
 * `ProtectedRoute` is unchanged — it still sends an unauthenticated visitor to
 * `/login`, not to `/`.
 */
export default function App() {
  return (
    <Routes>
      {/* --- Public marketing site (§2.6) --- */}
      <Route element={<PublicLayout />}>
        <Route path="/" element={<Home />} />
        <Route path="/what-is-doordoctor" element={<WhatIsDoorDoctor />} />
        <Route path="/who-its-for" element={<WhoItsFor />} />
        <Route path="/how-it-works" element={<HowItWorks />} />
        <Route path="/pricing" element={<Pricing />} />
        <Route path="/pricing/corporate" element={<PricingCorporate />} />
        <Route path="/pricing/institutions" element={<PricingInstitutions />} />
        <Route path="/nri" element={<Nri />} />
        <Route path="/about" element={<About />} />
        <Route path="/trust-and-safety" element={<TrustAndSafety />} />
        <Route path="/faq" element={<Faq />} />
        <Route path="/contact" element={<Contact />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
        {/* Unmatched paths land here, inside the public shell, so a wrong URL
            still arrives somewhere with navigation rather than at a dead end. */}
        <Route path="*" element={<NotFound />} />
      </Route>

      {/* --- Authentication --- */}
      <Route path="/login" element={<Login />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route path="/reset-password" element={<ResetPassword />} />

      {/* --- The product --- */}
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
        <Route path="care" element={<FamilyCareTeam />} />
        <Route path="care-circle" element={<FamilyCareCircle />} />
        <Route path="nurse/:nurseId" element={<FamilyNurseProfile />} />
        <Route path="labs" element={<FamilyLabs />} />
        <Route path="consults" element={<FamilyConsults />} />
        <Route path="alerts" element={<FamilyAlerts />} />
        <Route path="assistant" element={<FamilyAssistant />} />
        <Route path="reports" element={<FamilyReports />} />
        <Route path="plan" element={<MyPlan />} />
        <Route path="notifications" element={<FamilyNotifications />} />
        <Route path="privacy" element={<FamilyPrivacy />} />
      </Route>

      <Route
        path="/nurse"
        element={
          <ProtectedRoute allow={['nurse']}>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/nurse/my-day" replace />} />
        <Route path="my-day" element={<NurseMyDay />} />
        <Route path="roster" element={<NurseRoster />} />
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
        <Route path="care" element={<AdminCare />} />
        <Route path="escalations" element={<AdminEscalations />} />
        <Route path="labs" element={<AdminLabs />} />
        <Route path="visits" element={<AdminVisits />} />
        <Route path="board" element={<AdminVisitBoard />} />
        <Route path="alerts" element={<AdminAlerts />} />
        <Route path="outcomes" element={<AdminOutcomes />} />
        <Route path="zones" element={<AdminZones />} />
        <Route path="privacy" element={<AdminPrivacy />} />
        <Route path="assistant" element={<AdminAssistant />} />
        <Route path="subscriptions" element={<AdminSubscriptions />} />
        <Route path="revenue" element={<AdminRevenue />} />
        <Route path="leads" element={<AdminLeads />} />
      </Route>
    </Routes>
  )
}
