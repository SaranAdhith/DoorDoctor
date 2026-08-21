import { Navigate, useLocation } from 'react-router-dom'
import type { ReactNode } from 'react'

import type { Role } from '../types'
import { ROLE_HOME, useAuth } from './AuthContext'
import { LoadingScreen } from '../components/ui'

interface Props {
  allow: Role[]
  children: ReactNode
}

/**
 * Route guard. The backend enforces the same rules; this only keeps the UI
 * from showing a page the user cannot use.
 */
export function ProtectedRoute({ allow, children }: Props) {
  const { user, initialising } = useAuth()
  const location = useLocation()

  if (initialising) return <LoadingScreen label="Restoring your session" />
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (!allow.includes(user.role)) return <Navigate to={ROLE_HOME[user.role]} replace />

  return <>{children}</>
}
